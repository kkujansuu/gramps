# ------------------------------------------------------------------------
# RecentTags — Gramps addon
#
# Tracks recently used tags and patches EditTagList to show them at the
# top of the tag-selection dialog for quick access.
#
# Installation:
#   Place RecentTags.py + RecentTags.gpr.py in:
#       ~/.gramps/gramps51/plugins/RecentTags/
#   (adjust gramps51 to match your Gramps version directory)
#
# Compatibility: Gramps 5.x, 6.x  (GTK3 / Python 3)
# ------------------------------------------------------------------------

import json
import logging
import os

from gi.repository import Gtk

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.editors.edittaglist import EditTagList
from gramps.gui.plug import tool


class RecentTagsOptions(tool.ToolOptions):
    """Minimal options class required by the Gramps tool framework."""
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

log = logging.getLogger("RecentTags")

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_MAX_RECENT = 10
_JSON_PATH         = os.path.join(os.path.dirname(__file__), "recent-tags.json")


# ── Persistence ────────────────────────────────────────────────────────────────

def _load_all() -> dict:
    """Load the full JSON file.
    Structure:
    {
      "settings": { "max_recent": 10 },
      "<db_id>":  ["handle1", "handle2", ...]
    }
    """
    try:
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("RecentTags: could not read %s: %s", _JSON_PATH, exc)
    return {}


def _save_all(data: dict) -> None:
    """Write the full dict back to the JSON file."""
    try:
        with open(_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("RecentTags: could not write %s: %s", _JSON_PATH, exc)


def get_max_recent() -> int:
    """Return the user-configured maximum number of recent tags."""
    data = _load_all()
    return int(data.get("settings", {}).get("max_recent", DEFAULT_MAX_RECENT))


def set_max_recent(value: int) -> None:
    """Persist a new max_recent value, trimming existing lists if needed."""
    value = max(1, int(value))
    data  = _load_all()
    data.setdefault("settings", {})["max_recent"] = value
    # Trim all existing per-db lists to the new limit
    for key, val in data.items():
        if key != "settings" and isinstance(val, list):
            data[key] = val[:value]
    _save_all(data)


def _load_recent(db_id: str) -> list:
    """Return the list of recent tag handles for this database."""
    return _load_all().get(db_id, [])


def _record_tags_used(db_id: str, handles: list) -> None:
    """Move the supplied tag handles to the front of the recent list."""
    if not handles:
        return
    max_recent = get_max_recent()
    data   = _load_all()
    recent = data.get(db_id, [])
    for handle in reversed(handles):
        if handle in recent:
            recent.remove(handle)
        recent.insert(0, handle)
    data[db_id] = recent[:max_recent]
    _save_all(data)


# ── Preferences dialog ─────────────────────────────────────────────────────────

class RecentTagsPreferences(Gtk.Dialog):
    """Simple dialog to configure max_recent."""

    def __init__(self, parent=None):
        super().__init__(
            title=_("Recent Tags Preferences"),
            transient_for=parent,
            modal=True,
        )
        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("_OK"),     Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_border_width(12)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        self.get_content_area().pack_start(grid, True, True, 0)

        grid.attach(Gtk.Label(label=_("Maximum recent tags per database:"),
                              xalign=0.0), 0, 0, 1, 1)

        self._spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        self._spin.set_value(get_max_recent())
        self._spin.set_tooltip_text(_("Number of recently used tags to remember (1–50)"))
        grid.attach(self._spin, 1, 0, 1, 1)

        self.show_all()

    def run_and_apply(self):
        response = self.run()
        if response == Gtk.ResponseType.OK:
            set_max_recent(int(self._spin.get_value()))
        self.destroy()


def show_preferences(parent=None):
    """Entry point called by the plugin manager 'Preferences' button."""
    dlg = RecentTagsPreferences(parent=parent)
    dlg.run_and_apply()


class RecentTagsPreferencesTool(tool.Tool):
    """Tool entry point — opens the preferences dialog from Tools menu."""

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        show_preferences(parent=user.uistate.window if user.uistate else None)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _on_main_model_row_changed(main_model, path, iter_, recent_store):
    """
    Called whenever any row in the main ListStore changes.
    If it's a tag that exists in the recent store, mirror the checked state.
    """
    tag_name = main_model[path][2]
    checked  = main_model[path][1]
    for row in recent_store:
        if row[2] == tag_name:
            if row[1] != checked:
                row[1] = checked
            break


def _on_recent_cell_toggled(cell, path, model, dialog):
    """
    Toggle the checkbox in the recent TreeView and sync to the main model.
    The guard `if row[1] != checked` in _on_main_model_row_changed prevents
    an infinite signal loop.
    """
    model[path][1] = not model[path][1]
    tag_name = model[path][2]
    checked  = model[path][1]

    main_model = dialog.namemodel.model
    for row in main_model:
        if row[2] == tag_name:
            row[1] = checked
            break


def _build_recent_frame(dialog, recent_handles: list, full_list: list):
    """
    Build a 'Recent tags' Gtk.Frame containing a TreeView that mirrors
    the style of the main tag list (sort-key col hidden, toggle col, name col).

    recent_handles : list of tag handles in most-recent-first order.
    full_list      : list of (handle, name) tuples for all tags in the db.
    Returns the frame, or None if none of the recent handles exist in full_list.
    """
    handle_to_name = {item[0]: item[1] for item in full_list}

    # Current checked state from the main model
    checked_names = set()
    for row in dialog.namemodel.model:
        if row[1]:
            checked_names.add(row[2])

    # Build rows: only include handles that still exist in the database
    rows = []
    for handle in recent_handles:
        name = handle_to_name.get(handle)
        if name is not None:
            rows.append((name, name in checked_names, name))

    #if not rows:
    #    return None

    # ListStore: col0 = sort key (str), col1 = selected (bool), col2 = name (str)
    store = Gtk.ListStore(str, bool, str)
    for row in rows:
        store.append(row)

    view = Gtk.TreeView(model=store)
    view.set_headers_visible(False)
    view.set_enable_search(False)

    # Keep recent store in sync when the main list is toggled
    dialog.namemodel.model.connect("row-changed", _on_main_model_row_changed, store)

    # Hidden sort-key column (mirrors main list structure)
    col0 = Gtk.TreeViewColumn()
    col0.set_visible(False)
    view.append_column(col0)

    # Toggle column
    toggle_renderer = Gtk.CellRendererToggle()
    toggle_renderer.connect("toggled", _on_recent_cell_toggled, store, dialog)
    col1 = Gtk.TreeViewColumn(" ", toggle_renderer, active=1)
    col1.set_min_width(25)
    view.append_column(col1)

    # Tag name column
    text_renderer = Gtk.CellRendererText()
    col2 = Gtk.TreeViewColumn(_("Tag"), text_renderer, text=2)
    view.append_column(col2)

    # ScrolledWindow sized to fit rows (cap at 5 visible rows)
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    sw.set_min_content_height(min(len(rows), 5) * 22)
    sw.add(view)

    frame = Gtk.Frame(label=_("Recent tags"))
    frame.set_margin_bottom(6)
    frame.add(sw)

    return frame


# ── Monkey-patch ───────────────────────────────────────────────────────────────
# Guard against double-patching if Gramps reloads the plugin module,
# which would cause _orig_init to point to the already-patched version
# and recurse infinitely.

if getattr(EditTagList, "_recenttags_patched", False):
    log.info("RecentTags: already patched, skipping.")
else:
    _orig_init          = EditTagList.__init__
    _orig_create_dialog = EditTagList._create_dialog

    def _patched_init(self, tag_list, full_list, uistate, track):
        """
        Replacement __init__:
          1. Stash full_list and db_id for use by _patched_create_dialog.
          2. Run the original constructor (blocks until dialog closes).
          3. Record whichever tag handles the user accepted.
        """
        try:
            self._rt_db_id = uistate.viewmanager.dbstate.db.get_dbid()
        except Exception:
            self._rt_db_id = "__unknown__"

        self._rt_full_list = full_list

        _orig_init(self, tag_list, full_list, uistate, track)

        # _orig_init returns only after the dialog is closed.
        if self.return_list is not None:
            handles = [item[0] for item in self.return_list]  # item is (handle, name)
            _record_tags_used(self._rt_db_id, handles)

    def _patched_create_dialog(self):
        """
        Replacement _create_dialog: calls the original, then injects the
        recent-tags frame above the ScrolledWindow.
        """
        top = _orig_create_dialog(self)

        db_id     = getattr(self, "_rt_db_id", None)
        full_list = getattr(self, "_rt_full_list", [])

        if not db_id or not full_list:
            return top

        recent_handles = _load_recent(db_id)
#        if not recent_handles:
#            return top

        try:
            frame = _build_recent_frame(self, recent_handles, full_list)
            if frame is not None:
                children = top.vbox.get_children()
                slist = next(
                    (c for c in children if isinstance(c, Gtk.ScrolledWindow)), None
                )
                if slist is not None:
                    pos = children.index(slist)
                    top.vbox.pack_start(frame, False, False, 0)
                    top.vbox.reorder_child(frame, pos)
                    frame.show_all()
        except Exception as exc:
            log.warning("RecentTags: could not inject recent panel: %s", exc)

        return top

    EditTagList.__init__            = _patched_init
    EditTagList._create_dialog      = _patched_create_dialog
    EditTagList._recenttags_patched = True

    log.info("RecentTags: EditTagList patched successfully.")

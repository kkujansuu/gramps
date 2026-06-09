# tabledata_base.py
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024  (your name)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
tabledata_base  –  shared machinery for all TableData gramplets.

UI layout
=========
  [ + table ][ ✎ table ][ - table ]     ← table-level toolbar (top)
  ┌──────────────────────────────────┐
  │ Tab: "Measurements" │ "Links" │… │   ← Gtk.Notebook, one tab per table
  ├──────────────────────────────────┤
  │ [+ col][✎ col][- col] | [+ row]… │   ← per-table toolbar
  │ Col A  │  Col B  │  Col C        │
  │ …                                │
  └──────────────────────────────────┘

Each tab owns its own TreeView, ListStore, column list and sort state.

Database schema
===============
One SQLite file per family tree:  <tree_dir>/tabledata.db

  tables  (id INTEGER PK, object_type TEXT, tab_order INTEGER, name TEXT)

  columns (table_id INTEGER → tables.id,
           col_order INTEGER, name TEXT, col_type TEXT,
           PRIMARY KEY (table_id, col_order))

  rows    (table_id INTEGER → tables.id,
           object_handle TEXT,
           row_order INTEGER, col_order INTEGER, value TEXT,
           PRIMARY KEY (table_id, object_handle, row_order, col_order))

Column schema is per-table and shared across all objects.
Row data is per-table AND per-object (keyed by Gramps handle).

Stale-data strategy (Option B — startup purge only)
====================================================
When a Gramps object is deleted, its rows in tabledata.db are left alone
during that session.  This is deliberate: Gramps' undo stack is still live,
and hard-deleting rows immediately would lose data that the user could still
recover with Ctrl-Z.

At the start of the next session, post_init() calls _purge_orphaned_rows(),
which compares every stored handle against the set of handles that actually
exist in Gramps and permanently removes any that are gone.  By startup time
the previous session's undo stack has been discarded, so it is safe to do so.

Orphaned rows accumulate only within a single session and are invisible to
the user (there is no handle to select them by), so this is purely a storage
concern rather than a correctness concern.

Active-object tracking
=======================
Override active_changed(handle) — called by the Gramps framework via
_active_changed() whenever the active object changes.
connect_signal() is called in post_init() for non-Person nav types.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import subprocess
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Union

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from gramps.gen.plug import Gramplet
from gramps.gui.dialog import OkDialog

if TYPE_CHECKING:
    # These are GTK / Gramps types used only in annotations.
    # Importing them at runtime is fine; this block is just for clarity.
    from gi.repository import Gdk  # noqa: F401

# ODF/ODS support is optional — provided by the 'odfpy' package.
try:
    from odf.opendocument import OpenDocumentSpreadsheet, load as _ods_load
    from odf.table import (Table as _OdsTable, TableRow as _OdsRow,
                           TableCell as _OdsCell)
    from odf.text import P as _OdsP
    _HAVE_ODF: bool = True
except ImportError:
    _HAVE_ODF = False

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
# A column definition dict, e.g. {"col_order": 0, "name": "Height", "type": "Number"}
ColDef = dict[str, Any]
# A row dict, e.g. {"row_order": 0, "values": ["72.5", "kg"]}
RowData = dict[str, Any]
# A table definition dict, e.g. {"id": 1, "name": "Measurements"}
TableDef = dict[str, Any]

# ---------------------------------------------------------------------------
# Column-type constants
# ---------------------------------------------------------------------------
COL_TYPE_NUMBER: str = "Number"
COL_TYPE_STRING: str = "String"
COL_TYPE_URL: str    = "URL"
COL_TYPES: list[str] = [COL_TYPE_NUMBER, COL_TYPE_STRING, COL_TYPE_URL]

# GTK ListStore layout: col 0 = row_order (int, hidden), then one str per col
_META: int = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_number(text: str) -> Union[int, float]:
    """Parse *text* as an int, falling back to float.  Raises ValueError."""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return float(text)


def _db_path(dbstate: Any) -> str:
    """Return the absolute path to tabledata.db for the currently open tree."""
    return os.path.join(dbstate.db.get_save_path(), "tabledata.db")


# ---------------------------------------------------------------------------
# Database access layer
# ---------------------------------------------------------------------------
class _DB:
    """Thin sqlite3 wrapper; one instance is cached per tree path."""

    _cache: ClassVar[dict[str, _DB]] = {}

    # ------------------------------------------------------------------ cache
    @classmethod
    def get(cls, dbstate: Any) -> _DB:
        """Return the cached _DB for the current tree, creating it if needed."""
        path = _db_path(dbstate)
        if path not in cls._cache:
            cls._cache[path] = cls(path)
        return cls._cache[path]

    @classmethod
    def invalidate(cls, dbstate: Any) -> None:
        """Close and remove the cached connection for the current tree."""
        try:
            path = _db_path(dbstate)
        except Exception:
            return
        inst = cls._cache.pop(path, None)
        if inst is not None:
            try:
                inst._con.close()
            except Exception:
                pass

    # ------------------------------------------------------------------- init
    def __init__(self, path: str) -> None:
        self._con: sqlite3.Connection = sqlite3.connect(
            path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        # Must be set per-connection, outside executescript
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _schema_has_table_id(self) -> bool:
        """Return True if the *columns* table already has a *table_id* column."""
        cur = self._con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='columns'")
        if cur.fetchone() is None:
            return True   # fresh install — no old schema to worry about
        cur = self._con.execute("PRAGMA table_info(columns)")
        return any(row["name"] == "table_id" for row in cur)

    def _migrate(self) -> None:
        """Create or upgrade the database schema."""
        # Drop old single-table schema (columns keyed by object_type) if present.
        if not self._schema_has_table_id():
            self._con.executescript("""
                DROP TABLE IF EXISTS rows;
                DROP TABLE IF EXISTS columns;
            """)

        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS tables (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                object_type TEXT    NOT NULL,
                tab_order   INTEGER NOT NULL DEFAULT 0,
                name        TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS columns (
                table_id  INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
                col_order INTEGER NOT NULL,
                name      TEXT    NOT NULL,
                col_type  TEXT    NOT NULL DEFAULT 'String',
                PRIMARY KEY (table_id, col_order)
            );
            CREATE TABLE IF NOT EXISTS rows (
                table_id      INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
                object_handle TEXT    NOT NULL,
                row_order     INTEGER NOT NULL,
                col_order     INTEGER NOT NULL,
                value         TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (table_id, object_handle, row_order, col_order)
            );
            CREATE INDEX IF NOT EXISTS idx_rows_obj
                ON rows (table_id, object_handle);
        """)
        self._con.commit()
        # Re-enable after executescript (which resets per-connection PRAGMAs)
        self._con.execute("PRAGMA foreign_keys=ON")
    # ── tables ──────────────────────────────────────────────────────────────
    def get_tables(self, object_type: str) -> list[TableDef]:
        """Return all tables for *object_type*, ordered by tab_order then id."""
        cur = self._con.execute(
            "SELECT id, name FROM tables "
            "WHERE object_type=? ORDER BY tab_order, id",
            (object_type,))
        return [{"id": r["id"], "name": r["name"]} for r in cur]

    def add_table(self, object_type: str, name: str) -> int:
        """Insert a new table row and return its new id."""
        cur = self._con.execute(
            "SELECT COALESCE(MAX(tab_order)+1,0) FROM tables "
            "WHERE object_type=?", (object_type,))
        order: int = cur.fetchone()[0]
        cur = self._con.execute(
            "INSERT INTO tables (object_type, tab_order, name) VALUES (?,?,?)",
            (object_type, order, name))
        self._con.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def rename_table(self, table_id: int, name: str) -> None:
        self._con.execute("UPDATE tables SET name=? WHERE id=?",
                          (name, table_id))
        self._con.commit()

    def delete_table(self, table_id: int) -> None:
        """Delete a table; CASCADE removes its columns and rows automatically."""
        self._con.execute("DELETE FROM tables WHERE id=?", (table_id,))
        self._con.commit()

    # ── columns ─────────────────────────────────────────────────────────────
    def get_columns(self, table_id: int) -> list[ColDef]:
        """Return all column definitions for *table_id*, ordered by col_order."""
        cur = self._con.execute(
            "SELECT col_order, name, col_type FROM columns "
            "WHERE table_id=? ORDER BY col_order", (table_id,))
        return [{"col_order": r["col_order"],
                 "name":      r["name"],
                 "type":      r["col_type"]} for r in cur]

    def add_column(self, table_id: int, name: str, col_type: str) -> None:
        cur = self._con.execute(
            "SELECT COALESCE(MAX(col_order)+1,0) FROM columns "
            "WHERE table_id=?", (table_id,))
        order: int = cur.fetchone()[0]
        self._con.execute(
            "INSERT INTO columns (table_id, col_order, name, col_type) "
            "VALUES (?,?,?,?)", (table_id, order, name, col_type))
        self._con.commit()

    def update_column(self, table_id: int, col_order: int,
                      name: str, col_type: str) -> None:
        self._con.execute(
            "UPDATE columns SET name=?, col_type=? "
            "WHERE table_id=? AND col_order=?",
            (name, col_type, table_id, col_order))
        self._con.commit()

    def swap_columns(self, table_id: int, col_a: int, col_b: int) -> None:
        """Swap the positions of two columns (and their row data)."""
        TEMP: int = -1
        with self._con:
            for tbl in ("columns", "rows"):
                self._con.execute(
                    f"UPDATE {tbl} SET col_order=? "
                    "WHERE table_id=? AND col_order=?",
                    (TEMP, table_id, col_a))
                self._con.execute(
                    f"UPDATE {tbl} SET col_order=? "
                    "WHERE table_id=? AND col_order=?",
                    (col_a, table_id, col_b))
                self._con.execute(
                    f"UPDATE {tbl} SET col_order=? "
                    "WHERE table_id=? AND col_order=?",
                    (col_b, table_id, TEMP))

    def delete_column(self, table_id: int, col_order: int) -> None:
        """Delete a column and renumber the remaining columns."""
        with self._con:
            self._con.execute(
                "DELETE FROM columns WHERE table_id=? AND col_order=?",
                (table_id, col_order))
            self._con.execute(
                "DELETE FROM rows WHERE table_id=? AND col_order=?",
                (table_id, col_order))
            self._con.execute(
                "UPDATE columns SET col_order=col_order-1 "
                "WHERE table_id=? AND col_order>?",
                (table_id, col_order))
            self._con.execute(
                "UPDATE rows SET col_order=col_order-1 "
                "WHERE table_id=? AND col_order>?",
                (table_id, col_order))

    # ── rows ────────────────────────────────────────────────────────────────
    def get_rows(self, table_id: int, object_handle: str,
                 columns: list[ColDef]) -> list[RowData]:
        """Return all rows for *(table_id, object_handle)*, ordered by row_order."""
        if not columns:
            return []
        col_orders: list[int] = [c["col_order"] for c in columns]
        cur = self._con.execute(
            "SELECT row_order, col_order, value FROM rows "
            "WHERE table_id=? AND object_handle=? "
            "ORDER BY row_order, col_order",
            (table_id, object_handle))
        raw: dict[int, dict[int, str]] = {}
        for r in cur:
            raw.setdefault(r["row_order"], {})[r["col_order"]] = r["value"]
        return [{"row_order": ro,
                 "values": [raw[ro].get(co, "") for co in col_orders]}
                for ro in sorted(raw)]

    def purge_orphaned_rows(self, object_type: str,
                             live_handles: set[str]) -> int:
        """
        Hard-delete rows whose object_handle no longer exists in Gramps.

        Called once at startup, after the previous session's undo stack has
        been discarded, so it is safe to permanently remove data for any
        handle that Gramps no longer knows about.

        *live_handles* must be the complete set of handles that currently
        exist in Gramps for this object type.  As a safety guard, the method
        does nothing when *live_handles* is empty — an empty set passed by
        mistake would otherwise wipe all stored data.

        Returns the number of row-cells permanently removed.
        """
        if not live_handles:
            return 0

        cur = self._con.execute(
            "SELECT DISTINCT object_handle FROM rows "
            "WHERE table_id IN "
            "  (SELECT id FROM tables WHERE object_type=?)",
            (object_type,))
        stored: set[str] = {r[0] for r in cur}
        orphans: set[str] = stored - live_handles

        if not orphans:
            return 0

        ph = ",".join("?" * len(orphans))
        cur2 = self._con.execute(
            "SELECT COUNT(*) FROM rows "
            f"WHERE object_handle IN ({ph}) "
            "AND table_id IN "
            "  (SELECT id FROM tables WHERE object_type=?)",
            list(orphans) + [object_type])
        count: int = cur2.fetchone()[0]

        with self._con:
            self._con.execute(
                f"DELETE FROM rows WHERE object_handle IN ({ph}) "
                "AND table_id IN "
                "  (SELECT id FROM tables WHERE object_type=?)",
                list(orphans) + [object_type])

        return count


    def add_row(self, table_id: int, object_handle: str,
                columns: list[ColDef], values: list[str]) -> None:
        cur = self._con.execute(
            "SELECT COALESCE(MAX(row_order)+1,0) FROM rows "
            "WHERE table_id=? AND object_handle=?",
            (table_id, object_handle))
        ro: int = cur.fetchone()[0]
        with self._con:
            for col, val in zip(columns, values):
                self._con.execute(
                    "INSERT OR REPLACE INTO rows "
                    "(table_id, object_handle, row_order, col_order, value) "
                    "VALUES (?,?,?,?,?)",
                    (table_id, object_handle, ro, col["col_order"], val))

    def update_row(self, table_id: int, object_handle: str, row_order: int,
                   columns: list[ColDef], values: list[str]) -> None:
        with self._con:
            for col, val in zip(columns, values):
                self._con.execute(
                    "INSERT OR REPLACE INTO rows "
                    "(table_id, object_handle, row_order, col_order, value) "
                    "VALUES (?,?,?,?,?)",
                    (table_id, object_handle, row_order, col["col_order"], val))

    def delete_row(self, table_id: int, object_handle: str,
                   row_order: int) -> None:
        """Delete a row and compact row_order for the same object."""
        with self._con:
            self._con.execute(
                "DELETE FROM rows "
                "WHERE table_id=? AND object_handle=? AND row_order=?",
                (table_id, object_handle, row_order))
            self._con.execute(
                "UPDATE rows SET row_order=row_order-1 "
                "WHERE table_id=? AND object_handle=? AND row_order>?",
                (table_id, object_handle, row_order))


# ---------------------------------------------------------------------------
# Import / export helpers
# ---------------------------------------------------------------------------
def _ask_file_save(parent: Gtk.Window, title: str,
                   filters: list[tuple[str, str]]) -> Optional[str]:
    """Show a save-file dialog; return the chosen path or None."""
    dlg = Gtk.FileChooserDialog(
        title=title, transient_for=parent,
        action=Gtk.FileChooserAction.SAVE)
    dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_SAVE,   Gtk.ResponseType.OK)
    dlg.set_do_overwrite_confirmation(True)
    for name, pattern in filters:
        f = Gtk.FileFilter()
        f.set_name(name)
        f.add_pattern(pattern)
        dlg.add_filter(f)
    path: Optional[str] = None
    if dlg.run() == Gtk.ResponseType.OK:
        path = dlg.get_filename()
    dlg.destroy()
    return path


def _ask_file_open(parent: Gtk.Window, title: str,
                   filters: list[tuple[str, str]]) -> Optional[str]:
    """Show an open-file dialog; return the chosen path or None."""
    dlg = Gtk.FileChooserDialog(
        title=title, transient_for=parent,
        action=Gtk.FileChooserAction.OPEN)
    dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OPEN,   Gtk.ResponseType.OK)
    for name, pattern in filters:
        f = Gtk.FileFilter()
        f.set_name(name)
        f.add_pattern(pattern)
        dlg.add_filter(f)
    path: Optional[str] = None
    if dlg.run() == Gtk.ResponseType.OK:
        path = dlg.get_filename()
    dlg.destroy()
    return path


def _export_csv(path: str, columns: list[ColDef], rows: list[RowData]) -> None:
    """Write *columns* headers and *rows* data to a UTF-8 CSV file at *path*."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([c["name"] for c in columns])
        for row in rows:
            w.writerow(row["values"])


def _import_csv(path: str) -> tuple[list[str], list[list[str]]]:
    """Return *(header, data_rows)* parsed from a CSV file."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        all_rows: list[list[str]] = list(reader)
    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1:]


def _export_ods(path: str, table_name: str,
                columns: list[ColDef], rows: list[RowData]) -> None:
    """Write *columns* and *rows* to an ODS spreadsheet at *path*."""
    doc = OpenDocumentSpreadsheet()
    sheet = _OdsTable(name=table_name)
    doc.spreadsheet.addElement(sheet)

    def _cell(text: str) -> Any:
        tc = _OdsCell(valuetype="string")
        tc.addElement(_OdsP(text=str(text)))
        return tc

    hdr = _OdsRow()
    for col in columns:
        hdr.addElement(_cell(col["name"]))
    sheet.addElement(hdr)

    for row in rows:
        tr = _OdsRow()
        for val in row["values"]:
            tr.addElement(_cell(val))
        sheet.addElement(tr)

    doc.save(path)


def _import_ods(path: str) -> tuple[list[str], list[list[str]]]:
    """Return *(header, data_rows)* parsed from the first sheet of an ODS file."""
    doc = _ods_load(path)
    sheets = doc.spreadsheet.getElementsByType(_OdsTable)
    if not sheets:
        return [], []
    sheet = sheets[0]
    result: list[list[str]] = []
    for tr in sheet.getElementsByType(_OdsRow):
        cells = tr.getElementsByType(_OdsCell)
        row_vals: list[str] = []
        for tc in cells:
            ps = tc.getElementsByType(_OdsP)
            text = "".join(
                str(n) for p in ps
                for n in p.childNodes
                if n.nodeType == n.TEXT_NODE
            )
            row_vals.append(text)
        if any(row_vals):
            result.append(row_vals)
    if not result:
        return [], []
    return result[0], result[1:]


# ---------------------------------------------------------------------------
# Dialog: name a table (add or rename)
# ---------------------------------------------------------------------------
class _TableNameDialog(Gtk.Dialog):

    def __init__(self, parent: Gtk.Window,
                 title: str = "Table", name: str = "") -> None:
        super().__init__(title=title,
                         transient_for=parent,
                         flags=Gtk.DialogFlags.MODAL |
                               Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK,     Gtk.ResponseType.OK)
        self.set_default_size(300, -1)
        self.set_default_response(Gtk.ResponseType.OK)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                       margin_top=12, margin_bottom=8,
                       margin_start=12, margin_end=12)
        self.get_content_area().add(hbox)
        hbox.pack_start(Gtk.Label(label="Table name:", xalign=0),
                        False, False, 0)
        self._entry: Gtk.Entry = Gtk.Entry(text=name, activates_default=True,
                                           hexpand=True)
        hbox.pack_start(self._entry, True, True, 0)
        self.show_all()

    @property
    def table_name(self) -> str:
        return self._entry.get_text().strip()


# ---------------------------------------------------------------------------
# Dialog: define / rename a column
# ---------------------------------------------------------------------------
class _ColumnDialog(Gtk.Dialog):

    def __init__(self, parent: Gtk.Window,
                 name: str = "", col_type: str = COL_TYPE_STRING) -> None:
        super().__init__(title="Column",
                         transient_for=parent,
                         flags=Gtk.DialogFlags.MODAL |
                               Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK,     Gtk.ResponseType.OK)
        self.set_default_size(320, -1)
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6,
                        margin_top=12, margin_bottom=8,
                        margin_start=12, margin_end=12)
        self.get_content_area().add(grid)

        grid.attach(Gtk.Label(label="Column name:", xalign=0), 0, 0, 1, 1)
        self._name: Gtk.Entry = Gtk.Entry(text=name, activates_default=True,
                                          hexpand=True)
        grid.attach(self._name, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Data type:", xalign=0), 0, 1, 1, 1)
        self._type: Gtk.ComboBoxText = Gtk.ComboBoxText()
        for t in COL_TYPES:
            self._type.append_text(t)
        self._type.set_active(
            COL_TYPES.index(col_type) if col_type in COL_TYPES else 1)
        grid.attach(self._type, 1, 1, 1, 1)

        self.show_all()

    @property
    def col_name(self) -> str:
        return self._name.get_text().strip()

    @property
    def col_type(self) -> str:
        return self._type.get_active_text()


# ---------------------------------------------------------------------------
# Dialog: add / edit a row
# ---------------------------------------------------------------------------
class _RowDialog(Gtk.Dialog):

    def __init__(self, parent: Gtk.Window, columns: list[ColDef],
                 values: Optional[list[str]] = None) -> None:
        super().__init__(title="Row data",
                         transient_for=parent,
                         flags=Gtk.DialogFlags.MODAL |
                               Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK,     Gtk.ResponseType.OK)
        self.set_default_size(400, -1)
        self.set_default_response(Gtk.ResponseType.OK)

        if values is None:
            values = [""] * len(columns)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6,
                        margin_top=12, margin_bottom=8,
                        margin_start=12, margin_end=12)
        self.get_content_area().add(grid)

        self._entries: list[tuple[Gtk.Entry, str]] = []
        for i, (col, val) in enumerate(zip(columns, values)):
            name: str = col["name"]
            ctype: str = col["type"]
            grid.attach(Gtk.Label(label=f"{name} ({ctype}):", xalign=0),
                        0, i, 1, 1)
            entry = Gtk.Entry(text=val, activates_default=True, hexpand=True)
            if ctype == COL_TYPE_URL:
                entry.set_placeholder_text("https://…")
            elif ctype == COL_TYPE_NUMBER:
                entry.set_placeholder_text("0")
            grid.attach(entry, 1, i, 1, 1)
            self._entries.append((entry, ctype))

        self.show_all()

    def get_values(self) -> tuple[Optional[list[str]], str]:
        """Return *(values, error_message)*; error_message is '' on success."""
        out: list[str] = []
        for entry, ctype in self._entries:
            text = entry.get_text().strip()
            if ctype == COL_TYPE_NUMBER and text:
                try:
                    _to_number(text)
                except ValueError:
                    return None, f"'{text}' is not a valid number."
            out.append(text)
        return out, ""


# ---------------------------------------------------------------------------
# Per-table widget (one of these lives inside each notebook tab)
# ---------------------------------------------------------------------------
class _TableWidget(Gtk.Box):
    """
    A self-contained Box holding the column/row toolbar and TreeView for one
    table.  Owns its own column list, row list, and sort state.
    """

    def __init__(self, gramplet: "TableDataBase", table_id: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._gramplet: TableDataBase = gramplet
        self.table_id: int = table_id
        self._columns: list[ColDef] = []
        self._rows: list[RowData] = []
        self._sort_col: Optional[int] = None
        self._sort_asc: bool = True
        self._store: Optional[Gtk.ListStore] = None
        self._url_connected: bool = False

        # ── toolbar ──────────────────────────────────────────────────────
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                      margin_start=4, margin_end=4,
                      margin_top=4, margin_bottom=2)
        self.pack_start(bar, False, False, 0)

        def _btn(icon: str, tip: str) -> Gtk.Button:
            b = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
            b.set_image(Gtk.Image.new_from_icon_name(
                icon, Gtk.IconSize.SMALL_TOOLBAR))
            b.set_tooltip_text(tip)
            return b

        btn_add_col   = _btn("list-add",      "Add column")
        btn_del_col   = _btn("list-remove",   "Delete selected column")
        btn_edit_col  = _btn("document-edit", "Edit selected column")
        btn_col_left  = _btn("go-previous",   "Move selected column left")
        btn_col_right = _btn("go-next",       "Move selected column right")
        sep           = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        btn_add_row   = _btn("list-add",      "Add row")
        btn_del_row   = _btn("list-remove",   "Delete selected row")
        btn_edit_row  = _btn("document-edit", "Edit selected row")
        sep2          = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        btn_export    = _btn("document-save", "Export table to CSV or ODS")
        btn_import    = _btn("document-open", "Import rows from CSV or ODS")

        for w in (btn_add_col, btn_del_col, btn_edit_col,
                  btn_col_left, btn_col_right,
                  sep,
                  btn_add_row, btn_del_row, btn_edit_row,
                  sep2,
                  btn_export, btn_import):
            bar.pack_start(w, False, False, 0)

        btn_add_col  .connect("clicked", self._on_add_col)
        btn_del_col  .connect("clicked", self._on_del_col)
        btn_edit_col .connect("clicked", self._on_edit_col)
        btn_col_left .connect("clicked", self._on_move_col, -1)
        btn_col_right.connect("clicked", self._on_move_col, +1)
        btn_add_row  .connect("clicked", self._on_add_row)
        btn_del_row  .connect("clicked", self._on_del_row)
        btn_edit_row .connect("clicked", self._on_edit_row)
        btn_export   .connect("clicked", self._on_export)
        btn_import   .connect("clicked", self._on_import)

        # ── tree view ─────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._view: Gtk.TreeView = Gtk.TreeView(enable_search=False,
                                                rules_hint=True)
        scroll.add(self._view)
        self.pack_start(scroll, True, True, 0)

        self.show_all()

    # ------------------------------------------------------------------ load
    def load(self, handle: Optional[str]) -> None:
        """Reload columns and rows from the DB for *handle*."""
        db = self._gramplet._get_db()
        if db is None:
            self._columns = []
            self._rows    = []
        else:
            self._columns = db.get_columns(self.table_id)
            self._rows = (db.get_rows(self.table_id, handle, self._columns)
                          if handle else [])
        self._rebuild_view()

    # ------------------------------------------------------------------ view
    def _rebuild_view(self) -> None:
        for col in self._view.get_columns():
            self._view.remove_column(col)

        n: int = len(self._columns)
        if n == 0:
            self._store = Gtk.ListStore(int)
            self._view.set_model(self._store)
            return

        self._store = Gtk.ListStore(*([int] + [str] * n))
        self._view.set_model(self._store)

        for ci, col_def in enumerate(self._columns):
            store_ci: int = _META + ci
            ctype: str    = col_def["type"]

            renderer = Gtk.CellRendererText()
            if ctype == COL_TYPE_URL:
                renderer.set_property("foreground", "#1a6ed8")
                renderer.set_property("underline", Pango.Underline.SINGLE)

            tv_col = Gtk.TreeViewColumn(col_def["name"], renderer,
                                        text=store_ci)
            tv_col.set_resizable(True)
            tv_col.set_clickable(True)
            tv_col.set_sort_column_id(store_ci)
            tv_col.connect("clicked", self._on_header_clicked, ci)
            self._view.append_column(tv_col)

        self._apply_sort_indicator()

        if not self._url_connected:
            self._view.connect("button-release-event", self._on_view_click)
            self._url_connected = True

        self._populate_store()

    def _apply_sort_indicator(self) -> None:
        """Show the native GTK sort arrow on the active sort column."""
        for ci, tv_col in enumerate(self._view.get_columns()):
            if ci == self._sort_col:
                tv_col.set_sort_indicator(True)
                tv_col.set_sort_order(
                    Gtk.SortType.ASCENDING if self._sort_asc
                    else Gtk.SortType.DESCENDING)
            else:
                tv_col.set_sort_indicator(False)

    def _refresh_headers(self) -> None:
        self._apply_sort_indicator()

    def _populate_store(self) -> None:
        """Fill the ListStore from self._rows, applying the current sort."""
        assert self._store is not None
        self._store.clear()
        rows: list[RowData] = list(self._rows)

        if self._sort_col is not None and self._sort_col < len(self._columns):
            ctype: str = self._columns[self._sort_col]["type"]
            sc: int    = self._sort_col

            def _key(item: RowData) -> tuple[int, Any]:
                val: str = item["values"][sc] if sc < len(item["values"]) else ""
                if ctype == COL_TYPE_NUMBER:
                    try:
                        return (0, _to_number(val))
                    except (ValueError, TypeError):
                        return (1, 0)
                return (0, str(val).lower())

            rows.sort(key=_key, reverse=not self._sort_asc)

        for row in rows:
            store_row: list[Any] = [row["row_order"]]
            for ci in range(len(self._columns)):
                store_row.append(
                    row["values"][ci] if ci < len(row["values"]) else "")
            self._store.append(store_row)

    # ------------------------------------------------------------------ URL
    def _on_view_click(self, widget: Gtk.TreeView,
                       event: Any) -> bool:
        if event.button != 1:
            return False
        hit = self._view.get_path_at_pos(int(event.x), int(event.y))
        if hit is None:
            return False
        path, tv_col, _cx, _cy = hit
        cols = self._view.get_columns()
        if tv_col not in cols:
            return False
        ci: int = cols.index(tv_col)
        if ci >= len(self._columns):
            return False
        if self._columns[ci]["type"] != COL_TYPE_URL:
            return False
        assert self._store is not None
        it = self._store.get_iter(path)
        url: str = self._store.get_value(it, _META + ci).strip()
        if not url:
            return True
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", url])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                os.startfile(url)  # type: ignore[attr-defined]
        except Exception as exc:
            OkDialog("Cannot open URL", str(exc))
        return True

    # ------------------------------------------------------------------ sort
    def _on_header_clicked(self, _btn: Gtk.TreeViewColumn, ci: int) -> None:
        if self._sort_col == ci:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = ci
            self._sort_asc = True
        self._refresh_headers()
        self._populate_store()

    # ----------------------------------------------------------- column CRUD
    def _on_add_col(self, *_: Any) -> None:
        dlg  = _ColumnDialog(self._window())
        resp = dlg.run()
        name, ctype = dlg.col_name, dlg.col_type
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return
        db = self._gramplet._get_db()
        if db is None:
            return
        db.add_column(self.table_id, name, ctype)
        self.load(self._gramplet._current_handle)

    def _on_del_col(self, *_: Any) -> None:
        ci = self._focused_column()
        if ci is None:
            OkDialog("No column selected",
                     "Click a cell in the column you want to delete.")
            return
        col = self._columns[ci]
        dlg = Gtk.MessageDialog(
            transient_for=self._window(),
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=(f"Delete column '{col['name']}'?\n\n"
                  f"This removes this column's data for ALL "
                  f"{self._gramplet.object_type} objects."))
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return
        db = self._gramplet._get_db()
        if db is None:
            return
        db.delete_column(self.table_id, col["col_order"])
        if self._sort_col == ci:
            self._sort_col = None
        elif self._sort_col is not None and self._sort_col > ci:
            self._sort_col -= 1
        self.load(self._gramplet._current_handle)

    def _on_edit_col(self, *_: Any) -> None:
        ci = self._focused_column()
        if ci is None:
            OkDialog("No column selected",
                     "Click a cell in the column you want to edit.")
            return
        col = self._columns[ci]
        dlg = _ColumnDialog(self._window(),
                            name=col["name"], col_type=col["type"])
        resp = dlg.run()
        name, ctype = dlg.col_name, dlg.col_type
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return
        db = self._gramplet._get_db()
        if db is None:
            return
        db.update_column(self.table_id, col["col_order"], name, ctype)
        self.load(self._gramplet._current_handle)

    def _on_move_col(self, _btn: Gtk.Button, direction: int) -> None:
        """Move the focused column left (direction=-1) or right (+1)."""
        ci = self._focused_column()
        if ci is None:
            OkDialog("No column selected",
                     "Click a cell in the column you want to move.")
            return
        target_ci: int = ci + direction
        if target_ci < 0 or target_ci >= len(self._columns):
            return
        db = self._gramplet._get_db()
        if db is None:
            return
        col_a: int = self._columns[ci]["col_order"]
        col_b: int = self._columns[target_ci]["col_order"]
        db.swap_columns(self.table_id, col_a, col_b)
        if self._sort_col == ci:
            self._sort_col = target_ci
        elif self._sort_col == target_ci:
            self._sort_col = ci
        self.load(self._gramplet._current_handle)
        cols = self._view.get_columns()
        if target_ci < len(cols):
            self._view.set_cursor(
                Gtk.TreePath.new_first(), cols[target_ci], False)

    # ------------------------------------------------------------- row CRUD
    def _on_add_row(self, *_: Any) -> None:
        if not self._gramplet._require_handle():
            return
        if not self._columns:
            OkDialog("No columns", "Add at least one column first.")
            return
        dlg  = _RowDialog(self._window(), self._columns)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            values, err = dlg.get_values()
            if err:
                dlg.destroy()
                OkDialog("Invalid data", err)
                return
            db = self._gramplet._get_db()
            if db and values is not None:
                db.add_row(self.table_id,
                           self._gramplet._current_handle,  # type: ignore[arg-type]
                           self._columns, values)
            self.load(self._gramplet._current_handle)
        dlg.destroy()

    def _on_del_row(self, *_: Any) -> None:
        if not self._gramplet._require_handle():
            return
        ro = self._selected_row_order()
        if ro is None:
            OkDialog("No row selected", "Select a row to delete.")
            return
        db = self._gramplet._get_db()
        if db:
            db.delete_row(self.table_id,
                          self._gramplet._current_handle,  # type: ignore[arg-type]
                          ro)
        self.load(self._gramplet._current_handle)

    def _on_edit_row(self, *_: Any) -> None:
        if not self._gramplet._require_handle():
            return
        ro = self._selected_row_order()
        if ro is None:
            OkDialog("No row selected", "Select a row to edit.")
            return
        current: Optional[RowData] = next(
            (r for r in self._rows if r["row_order"] == ro), None)
        values: list[str] = current["values"] if current else []
        dlg  = _RowDialog(self._window(), self._columns, values=list(values))
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            new_values, err = dlg.get_values()
            if err:
                dlg.destroy()
                OkDialog("Invalid data", err)
                return
            db = self._gramplet._get_db()
            if db and new_values is not None:
                db.update_row(self.table_id,
                              self._gramplet._current_handle,  # type: ignore[arg-type]
                              ro, self._columns, new_values)
            self.load(self._gramplet._current_handle)
        dlg.destroy()

    # --------------------------------------------------------- import/export
    def _on_export(self, *_: Any) -> None:
        if not self._columns:
            OkDialog("Nothing to export", "Add columns first.")
            return
        filters: list[tuple[str, str]] = [("CSV files", "*.csv")]
        if _HAVE_ODF:
            filters.append(("ODS spreadsheet", "*.ods"))
        filters.append(("All files", "*"))

        path = _ask_file_save(self._window(), "Export table", filters)
        if not path:
            return

        ext: str = os.path.splitext(path)[1].lower()
        if ext not in (".csv", ".ods"):
            path += ".csv"
            ext = ".csv"

        if ext == ".ods" and not _HAVE_ODF:
            OkDialog("ODS not available",
                     "The 'odfpy' package is not installed.\n"
                     "Install it with:  pip install odfpy\n"
                     "Exporting as CSV instead.")
            path = os.path.splitext(path)[0] + ".csv"
            ext = ".csv"

        try:
            rows: list[RowData] = (self._rows
                                   if self._gramplet._current_handle else [])
            if ext == ".csv":
                _export_csv(path, self._columns, rows)
            else:
                db = self._gramplet._get_db()
                tname: str = "Table"
                if db:
                    tables = db.get_tables(self._gramplet.object_type)
                    tname = next(
                        (t["name"] for t in tables
                         if t["id"] == self.table_id), "Table")
                _export_ods(path, tname, self._columns, rows)
            OkDialog("Export complete", f"Saved to:\n{path}")
        except Exception as exc:
            OkDialog("Export failed", str(exc))

    def _on_import(self, *_: Any) -> None:
        if not self._gramplet._require_handle():
            return

        filters: list[tuple[str, str]] = [("CSV files", "*.csv")]
        if _HAVE_ODF:
            filters.append(("ODS spreadsheet", "*.ods"))
        filters.append(("All files", "*"))

        path = _ask_file_open(self._window(), "Import table", filters)
        if not path:
            return

        ext: str = os.path.splitext(path)[1].lower()

        try:
            if ext == ".ods":
                if not _HAVE_ODF:
                    OkDialog("ODS not available",
                             "The 'odfpy' package is not installed.\n"
                             "Install it with:  pip install odfpy")
                    return
                header, data_rows = _import_ods(path)
            else:
                header, data_rows = _import_csv(path)
        except Exception as exc:
            OkDialog("Import failed", str(exc))
            return

        if not header:
            OkDialog("Import failed", "File is empty or has no header row.")
            return

        db = self._gramplet._get_db()
        if db is None:
            return

        # Map file columns to existing columns by name; add missing ones.
        existing: dict[str, ColDef] = {
            c["name"].lower(): c for c in self._columns}
        file_to_col: list[ColDef] = []

        for h in header:
            key = h.strip().lower()
            if key in existing:
                file_to_col.append(existing[key])
            else:
                db.add_column(self.table_id, h.strip(), COL_TYPE_STRING)
                self._columns = db.get_columns(self.table_id)
                existing = {c["name"].lower(): c for c in self._columns}
                file_to_col.append(existing[h.strip().lower()])

        dlg = Gtk.MessageDialog(
            transient_for=self._window(),
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=(f"Import {len(data_rows)} row(s) into this table?\n\n"
                  f"Columns matched: {len(file_to_col)}\n"
                  "Existing rows will be kept; imported rows are appended."))
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return

        handle: str = self._gramplet._current_handle  # type: ignore[assignment]
        imported: int = 0
        errors: int   = 0
        for data_row in data_rows:
            vals: list[str] = (list(data_row) + [""] * len(file_to_col))
            vals = vals[:len(file_to_col)]
            ok: bool = True
            cleaned: list[str] = []
            for col, val in zip(file_to_col, vals):
                val = val.strip()
                if col["type"] == COL_TYPE_NUMBER and val:
                    try:
                        _to_number(val)
                    except ValueError:
                        errors += 1
                        ok = False
                        break
                cleaned.append(val)
            if ok:
                db.add_row(self.table_id, handle, file_to_col, cleaned)
                imported += 1

        self.load(handle)
        msg: str = f"Imported {imported} row(s)."
        if errors:
            msg += f"\n{errors} row(s) skipped due to invalid number values."
        OkDialog("Import complete", msg)

    # ---------------------------------------------------------------- helpers
    def _selected_row_order(self) -> Optional[int]:
        """Return the DB row_order of the selected row, or None."""
        model, it = self._view.get_selection().get_selected()
        if it is None:
            return None
        return model.get_value(it, 0)

    def _focused_column(self) -> Optional[int]:
        """Return the visual column index of the focused cell, or None."""
        _, tv_col = self._view.get_cursor()
        if tv_col is None:
            return None
        cols = self._view.get_columns()
        return cols.index(tv_col) if tv_col in cols else None

    def _window(self) -> Gtk.Window:
        return self._view.get_toplevel()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Base gramplet
# ---------------------------------------------------------------------------
class TableDataBase(Gramplet):
    """
    Base class for all TableData gramplets.

    Subclasses must set the class attribute:
        object_type: str = "Person"   # or Family / Event / Place / …
    """

    object_type: str = "Unknown"

    # -----------------------------------------------------------------------
    # Gramplet lifecycle
    # -----------------------------------------------------------------------
    def init(self) -> None:
        self._current_handle: Optional[str] = None
        self._tab_widgets: dict[int, _TableWidget] = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── table-level toolbar ───────────────────────────────────────────
        tbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                       margin_start=4, margin_end=4,
                       margin_top=4, margin_bottom=2)

        def _btn(icon: str, tip: str) -> Gtk.Button:
            b = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
            b.set_image(Gtk.Image.new_from_icon_name(
                icon, Gtk.IconSize.SMALL_TOOLBAR))
            b.set_tooltip_text(tip)
            return b

        btn_add_tbl = _btn("list-add",      "Add table")
        btn_ren_tbl = _btn("document-edit", "Rename current table")
        btn_del_tbl = _btn("list-remove",   "Delete current table")

        for w in (btn_add_tbl, btn_ren_tbl, btn_del_tbl):
            tbar.pack_start(w, False, False, 0)

        btn_add_tbl.connect("clicked", self._on_add_table)
        btn_ren_tbl.connect("clicked", self._on_rename_table)
        btn_del_tbl.connect("clicked", self._on_delete_table)

        root.pack_start(tbar, False, False, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        # ── status label ─────────────────────────────────────────────────
        self._status_lbl: Gtk.Label = Gtk.Label(
            xalign=0, margin_start=6, margin_bottom=2)
        root.pack_start(self._status_lbl, False, False, 0)

        # ── notebook ─────────────────────────────────────────────────────
        self._notebook: Gtk.Notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_show_border(False)
        root.pack_start(self._notebook, True, True, 0)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()

    def post_init(self) -> None:
        if self.object_type != "Person":
            self.connect_signal(self.object_type, self._active_changed)

        # Option B: purge orphaned rows once at startup.
        # By the time post_init() runs, the previous session's undo stack
        # has been discarded by Gramps, so any handle that no longer exists
        # in the tree is truly gone and safe to clean up permanently.
        # We do NOT connect to delete/add signals — that would race with
        # Gramps' own undo stack and risk destroying data that the user
        # could still recover via Ctrl-Z.
        self._purge_orphaned_rows()

        handle: Optional[str] = self.get_active(self.object_type) or None
        self._reload(handle)

    def active_changed(self, handle: str) -> None:
        """Called by the Gramps framework when the active object changes."""
        self._reload(handle or None)

    def main(self) -> None:
        """Initial load / called by Gramps for Person gramplets."""
        handle: Optional[str] = self.get_active(self.object_type) or None
        self._reload(handle)

    def db_changed(self) -> None:
        """Called when the family tree is opened, closed, or replaced."""
        _DB.invalidate(self.dbstate)
        self._tab_widgets.clear()
        self._reload(None)

    def _purge_orphaned_rows(self) -> None:
        """
        Remove rows for handles that no longer exist in Gramps.

        Safe to call at startup: Gramps discards the previous session's
        undo stack when it opens a tree, so any stale handle is permanently
        gone.  We never call this during a live session — deleting a person
        and then hitting Undo should restore their rows intact.
        """
        db = self._get_db()
        if db is None:
            return
        try:
            _ITER_FN: dict[str, str] = {
                "Person":     "iter_person_handles",
                "Family":     "iter_family_handles",
                "Event":      "iter_event_handles",
                "Place":      "iter_place_handles",
                "Source":     "iter_source_handles",
                "Citation":   "iter_citation_handles",
                "Repository": "iter_repository_handles",
                "Media":      "iter_media_handles",
            }
            iter_fn = getattr(
                self.dbstate.db,
                _ITER_FN.get(self.object_type, ""),
                None)
            if iter_fn is None:
                return
            live_handles: set[str] = set(iter_fn())
            removed = db.purge_orphaned_rows(self.object_type, live_handles)
            if removed:
                import logging
                logging.getLogger(__name__).info(
                    "TableData: purged %d orphaned row-cells for %s",
                    removed, self.object_type)
        except Exception:
            pass  # never crash the gramplet over a cleanup operation

    # -----------------------------------------------------------------------
    # Reload
    # -----------------------------------------------------------------------
    def _reload(self, handle: Optional[str]) -> None:
        self._current_handle = handle

        db = self._get_db()
        if db is None:
            self._set_status("(no database open)")
            self._rebuild_notebook([])
            return

        tables: list[TableDef] = db.get_tables(self.object_type)
        self._set_status("" if handle else f"No {self.object_type} selected")
        self._rebuild_notebook(tables)

    def _rebuild_notebook(self, tables: list[TableDef]) -> None:
        """Synchronise the Gtk.Notebook to match *tables*."""
        current_page: int = self._notebook.get_current_page()
        old_ids: list[int] = list(self._tab_widgets)
        current_id: Optional[int] = (
            old_ids[current_page]
            if 0 <= current_page < len(old_ids) else None)

        while self._notebook.get_n_pages() > 0:
            self._notebook.remove_page(0)

        existing_ids: set[int] = {t["id"] for t in tables}
        for tid in list(self._tab_widgets):
            if tid not in existing_ids:
                del self._tab_widgets[tid]

        restore_page: int = 0
        for i, tbl in enumerate(tables):
            tid: int = tbl["id"]
            if tid not in self._tab_widgets:
                tw = _TableWidget(self, tid)
                self._tab_widgets[tid] = tw
            else:
                tw = self._tab_widgets[tid]

            tw.load(self._current_handle)
            self._notebook.append_page(tw, Gtk.Label(label=tbl["name"]))
            tw.show_all()

            if tid == current_id:
                restore_page = i

        if tables:
            self._notebook.set_current_page(restore_page)

        self._notebook.show_all()

    # -----------------------------------------------------------------------
    # Table CRUD
    # -----------------------------------------------------------------------
    def _on_add_table(self, *_: Any) -> None:
        dlg  = _TableNameDialog(self._window(), title="Add Table")
        resp = dlg.run()
        name: str = dlg.table_name
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return
        db = self._get_db()
        if db is None:
            return
        db.add_table(self.object_type, name)
        self._reload(self._current_handle)
        last: int = self._notebook.get_n_pages() - 1
        if last >= 0:
            self._notebook.set_current_page(last)

    def _on_rename_table(self, *_: Any) -> None:
        tid = self._current_table_id()
        if tid is None:
            OkDialog("No table", "Add a table first.")
            return
        db = self._get_db()
        if db is None:
            return
        tables = db.get_tables(self.object_type)
        current_name: str = next(
            (t["name"] for t in tables if t["id"] == tid), "")
        dlg  = _TableNameDialog(self._window(),
                                title="Rename Table", name=current_name)
        resp = dlg.run()
        name: str = dlg.table_name
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not name:
            return
        db.rename_table(tid, name)
        self._reload(self._current_handle)

    def _on_delete_table(self, *_: Any) -> None:
        tid = self._current_table_id()
        if tid is None:
            OkDialog("No table", "Add a table first.")
            return
        db = self._get_db()
        if db is None:
            return
        tables = db.get_tables(self.object_type)
        tname: str = next(
            (t["name"] for t in tables if t["id"] == tid), "?")
        dlg = Gtk.MessageDialog(
            transient_for=self._window(),
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=(f"Delete table '{tname}'?\n\n"
                  "This permanently removes the table, all its columns, "
                  f"and all its data for every {self.object_type} object."))
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return
        db.delete_table(tid)
        del self._tab_widgets[tid]
        self._reload(self._current_handle)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _current_table_id(self) -> Optional[int]:
        """Return the table_id of the currently visible notebook tab."""
        page: int = self._notebook.get_current_page()
        if page < 0:
            return None
        widget = self._notebook.get_nth_page(page)
        return widget.table_id if isinstance(widget, _TableWidget) else None

    def _require_handle(self) -> bool:
        """Return True if an object is selected; show an error dialog otherwise."""
        if self._current_handle:
            return True
        OkDialog("No object selected",
                 f"Please select a {self.object_type} first.")
        return False

    def _get_db(self) -> Optional[_DB]:
        """Return the _DB instance for the current tree, or None."""
        try:
            return _DB.get(self.dbstate)
        except Exception:
            return None

    def _set_status(self, text: str) -> None:
        self._status_lbl.set_text(text)
        self._status_lbl.set_visible(bool(text))

    def _window(self) -> Gtk.Window:
        return self._notebook.get_toplevel()  # type: ignore[return-value]

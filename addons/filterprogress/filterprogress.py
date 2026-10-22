#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      Kari Kujansuu
# Copyright (C) 2026      Claude AI (wish coding by Brian McCullough)
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
#
"""
Filter Progress: a progress window with a working Cancel button while a
filter runs.

Gramps 5.2 shows a progress window for filters, but without Cancel.
Gramps 6.0 to 6.1 (and master, as of October 2026) show none: the
begin_progress() call in GenericFilter.apply_logical_op_to_all() is
commented out. This module replaces the relevant GenericFilter methods:
check_func() and check_and() on 5.2, apply_logical_op_to_all() on 6.0.2
and later.

Importing this module changes nothing. The replacements are installed by
load_on_reg(), which Gramps calls once at startup (see
filterprogress.gpr.py).

Diagnostics go through the logger ".filterprogress", never print().
Gramps writes WARNING and above to the terminal with the file name and
line number, so their origin is always visible. DEBUG messages appear
only when Gramps is started with:  gramps -d ".filterprogress"
"""

# ------------------------
# Python modules
# ------------------------
import logging

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters._genericfilter import GenericFilter
from gramps.version import VERSION_TUPLE

_ = glocale.translation.gettext

LOG = logging.getLogger(".filterprogress")


def _progress_meter(total):
    """
    Open a progress window with a Cancel button.

    Imported here, not at module level, so the module can be imported
    without a display (for example by a command-line run of Gramps).

    :param total: number of steps the bar represents.
    :returns: the open ProgressMeter.
    """
    # pylint: disable-next=import-outside-toplevel
    from gramps.gui.utils import ProgressMeter

    progress = ProgressMeter(_("Filter"), can_cancel=True)
    progress.set_pass(header=_("Applying ..."), total=total)
    return progress


# ------------------------------------------------------------
#
# Gramps 5.2: check_func() and check_and()
#
# ------------------------------------------------------------
def new_check_func(self, db, id_list, task, user=None, tupleind=None, tree=False):
    """Replacement for GenericFilter.check_func() (Gramps 5.2)."""
    final_list = []
    progress = _progress_meter(self.get_number(db)) if user else None
    if id_list is None:
        with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
            for handle, data in cursor:
                person = self.make_obj()
                person.unserialize(data)
                if progress and progress.step():
                    LOG.debug("check_func: canceled by the user")
                    break
                if task(db, person) != self.invert:
                    final_list.append(handle)
    else:
        for data in id_list:
            handle = data if tupleind is None else data[tupleind]
            person = self.find_from_handle(db, handle)
            if progress and progress.step():
                LOG.debug("check_func: canceled by the user")
                break
            if task(db, person) != self.invert:
                final_list.append(data)
    if progress:
        progress.close()
    return final_list


def new_check_and(self, db, id_list, user=None, tupleind=None, tree=False):
    """Replacement for GenericFilter.check_and() (Gramps 5.2)."""
    final_list = []
    flist = self.flist
    progress = _progress_meter(self.get_number(db)) if user else None
    if id_list is None:
        with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
            for handle, data in cursor:
                person = self.make_obj()
                person.unserialize(data)
                if progress and progress.step():
                    LOG.debug("check_and: canceled by the user")
                    break
                val = all(rule.apply(db, person) for rule in flist)
                if val != self.invert:
                    final_list.append(handle)
    else:
        for data in id_list:
            handle = data if tupleind is None else data[tupleind]
            person = self.find_from_handle(db, handle)
            if progress and progress.step():
                LOG.debug("check_and: canceled by the user")
                break
            val = all(rule.apply(db, person) for rule in flist if person)
            if val != self.invert:
                final_list.append(data)
    if progress:
        progress.close()
    return final_list


# ------------------------------------------------------------
#
# Gramps 6.0.2 and later: apply_logical_op_to_all()
#
# ------------------------------------------------------------
def new_apply_logical_op_to_all(
    self,
    db,
    possible_handles,  # Set[PrimaryObjectHandle]
    apply_logical_op,
    user=None,
):
    """Replacement for GenericFilter.apply_logical_op_to_all() (6.0.2+)."""
    # pylint: disable-next=import-outside-toplevel
    from gramps.gen.filters.optimizer import Optimizer

    total = len(possible_handles)
    LOG.debug("apply_logical_op_to_all: %d possible handles, user=%r", total, user)

    # Optimizer() takes the filter from 6.0.4 on.
    optimizer = Optimizer(self) if VERSION_TUPLE >= (6, 0, 4) else Optimizer()
    handles_in, handles_out = optimizer.compute_potential_handles_for_filter(self)

    # The bar moves in 100 steps rather than one per handle, so a large
    # tree does not spend its time redrawing the window.
    progress = _progress_meter(100) if user else None
    step_every = max(total // 100, 1)

    final_list = []
    for count, handle in enumerate(possible_handles):
        # Step before the optimizer skips below, so the bar reaches the
        # end even when most handles are skipped.
        if progress and count % step_every == 0 and progress.step():
            LOG.debug(
                "apply_logical_op_to_all: canceled by the user after %d of %d",
                count,
                total,
            )
            break
        if handles_in is not None and handle not in handles_in:
            continue
        if handles_out is not None and handle in handles_out:
            continue
        obj = self.get_object(db, handle)
        if apply_logical_op(db, obj, self.flist) != self.invert:
            final_list.append(obj.handle)

    if progress:
        progress.close()
    return final_list


# ------------------------------------------------------------
#
# Installation, called by Gramps at startup
#
# ------------------------------------------------------------
def load_on_reg(_dbstate, _uistate, _plugin):
    """
    Install the replacement methods on GenericFilter.

    Called once by Gramps at startup, because the registration sets
    load_on_reg=True. Only methods that exist in the running Gramps are
    replaced.

    :returns: an empty list (Gramps stores it as the plugin's data).
    """
    if VERSION_TUPLE >= (6, 0, 2):
        GenericFilter.apply_logical_op_to_all = new_apply_logical_op_to_all
        LOG.debug("installed apply_logical_op_to_all replacement")
    elif hasattr(GenericFilter, "check_func"):
        GenericFilter.check_func = new_check_func
        GenericFilter.check_and = new_check_and
        LOG.debug("installed check_func/check_and replacements")
    else:
        LOG.warning(
            "Filter Progress: this Gramps version has none of the filter "
            "methods it replaces; nothing installed"
        )
    return []

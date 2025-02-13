"""
    This addon will add a 'Merge' button in the embedded childlist in the Family Editor.
"""    

#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      Kari Kujansuu
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

import traceback

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

from gi.repository import Gtk

from gramps.gui.dialog import ErrorDialog
from gramps.gui.editors import EditFamily
from gramps.gui.merge import MergePerson
from gramps.gui.widgets import SimpleButton


# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


def merge(dbstate, uistate, selection):
    model, treepaths = selection.get_selected_rows()
    handles = []
    for treepath in treepaths:
        row = list(model[treepath])
        childref = row[-1]
        handles.append(childref.ref)
    if len(handles) != 2:
        ErrorDialog("Error", "Merge exactly two persons")
        return
    MergePerson(dbstate, uistate, [], handles[0], handles[1])

    
def load_on_reg(dbstate, uistate, plugin):
    # patch some classes
    traceback.print_stack()
    def new_post_init(self, cls):
        cls.orig_post_init(self)
        hbox = self.child_list.add_btn.get_parent()
        merge_button = SimpleButton("gramps-merge", lambda _button: merge(dbstate, uistate, selection))
        merge_button.set_sensitive(False)
        hbox.pack_start(merge_button, False, False, 20)
        hbox.show_all()
        selection = self.child_list.tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.get_selected = lambda: get_selected(selection)
        selection.select_path = lambda *x: False  # no-op to enable multiple selection, otherwise the select_path calls will interfere
        selection.connect("changed", lambda selection: selection_changed(selection, merge_button))
    for cls in [EditFamily]:
        if not hasattr(cls, "orig_post_init"):
             cls.orig_post_init = cls._post_init
        cls._post_init = lambda self, cls=cls: new_post_init(self, cls)
        
def selection_changed(selection, merge_button):
    merge_button.set_sensitive(len(selection.get_selected_rows()[1]) == 2)

def get_selected(selection):
    """
    Emulate 'get_selected' for selections with SelectionMode.MULTIPLE: return the first selected row
    """
    model, treepaths = selection.get_selected_rows()
    for treepath in treepaths:
        return model, model.get_iter(treepath)
    return model, None 



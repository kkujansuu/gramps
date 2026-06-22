#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Kari Kujansuu
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
    This addon will change the Database Manager dialog so that the selected database is always visible 
    even after sorting the list by clicking the column headers.
"""    

import csv
import io
import json
import traceback

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

from gi.repository import Gtk, Gdk

from gramps.gui.dbman import DbManager

cls = DbManager

def load_on_reg(dbstate, uistate, plugin):
    if not hasattr(cls, "orig_init"):
         cls.orig_init = cls.__init__
    cls.__init__ = new_init 


def new_init(self, *args, **kwargs):
    cls.orig_init(self, *args, **kwargs)
    for column in self.dblist.get_columns():
        column.connect("clicked", lambda *args: scroll_to_selected_row(self))

def scroll_to_selected_row(self):
    store, node = self.selection.get_selected()
    tree_path = store.get_path(node)
    self.dblist.scroll_to_cell(tree_path, None, False, 0.5, 0.5)
        


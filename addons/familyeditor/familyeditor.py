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

# Adds parents' birth and death places in the Family Editor


# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
import os
import sys
import time
import traceback

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.display.place import displayer as place_displayer
from gramps.gui.editors.editfamily import EditFamily

cls = EditFamily

def load_on_reg(dbstate, uistate, plugin):
    if not hasattr(cls, "orig_update_father"):
         cls.orig_update_father = cls.update_father
    cls.update_father = new_update_father
    
    if not hasattr(cls, "orig_update_mother"):
         cls.orig_update_mother = cls.update_mother
    cls.update_mother = new_update_mother

def new_update_father(self, handle):
    cls.orig_update_father(self, handle)
    update_parent(self, handle, "f")

def new_update_mother(self, handle):
    cls.orig_update_mother(self, handle)
    update_parent(self, handle, "m")

def update_parent(self, handle, prefix):
    if handle is None: return
    person = self.dbstate.db.get_person_from_handle(handle)
    bplace = get_event_place(self, person.get_birth_ref())
    if bplace:
        birth = self.top.get_object(prefix + "birth")
        bdate = birth.get_text()
        birth.set_text(bdate + " " + bplace)
    dplace = get_event_place(self, person.get_death_ref())
    if dplace:
        death = self.top.get_object(prefix + "death")
        ddate = death.get_text()
        death.set_text(ddate + " " + dplace)


def get_event_place(self, eventref):
    if not eventref: return ""
    event = self.dbstate.db.get_event_from_handle(eventref.ref)
    return place_displayer.display_event(self.dbstate.db, event)


#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024-2025      Kari Kujansuu
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
Patches some Gramps internal classes so the that a person's display name contains also the surnames defined in alternate names.

For example, consider a person with

    Primary name (type MARRIED):
      First name: Mary 
      Last name:  Smith
    Alternate name (type BIRTH):
      First name: Mary 
      Last name:  Jones

Normally her display name is derived from the primary name only. It could be for example "Mary Smith". 

When this addon is installed then her name is displayed as "Mary Smith (Jones)" - the alternate surname is added at the end of the name in parentheses. This is not possible in regular Gramps.

If a person does not have alternate names (or the alternate names do not contain surnames) then the display name is not changed.

If there are multiple alternate names then all the surnames are listed separated by commas, for example "Mary Smith (Jones, Hill).

If the name format set in Gramps settings is e.g. "Surname, Given" then the alternate names are still appended at the end: "Smith, Mary (Jones)".

However, this does not affect all places in Gramps where names are displayed. At least some reports seem to use their own way to display names.

The new format name is not stored in the database. The new names are generated in the runtime. If this addon is removed then the original name format will again be used.

"""
# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

from gramps.gen.const import VERSION_TUPLE
from gramps.gen.lib import Person, Name
from gramps.gen.display.name import NameDisplay
from gramps.gui.views.treemodels import PeopleBaseModel, FamilyModel

def load_on_reg(dbstate, uistate, plugin):
    # patch some classes
    
    # NameDisplay.display is used in relationship view, in charts and in the title in the person editor dialog
    if not hasattr(NameDisplay, "orig_display"):
        NameDisplay.orig_display = NameDisplay.display
    NameDisplay.display = new_display

    # PeopleBaseModel.column_name is used in people list view
    if not hasattr(PeopleBaseModel, "orig_column_name"):
        PeopleBaseModel.orig_column_name = PeopleBaseModel.column_name
    PeopleBaseModel.column_name = new_column_name

    # FamilyModel.column_father is used in family list view
    if not hasattr(FamilyModel, "orig_column_father"):
        FamilyModel.orig_column_father = FamilyModel.column_father
    FamilyModel.column_father = new_column_father

    # FamilyModel.column_mother is used in family list view
    if not hasattr(FamilyModel, "orig_column_mother"):
        FamilyModel.orig_column_mother = FamilyModel.column_mother
    FamilyModel.column_mother = new_column_mother


def new_display(self, person):
    orig_name = NameDisplay.orig_display(self, person)
    return get_new_name(person, orig_name)

if VERSION_TUPLE < (6, 0, 0):
    def new_column_name(self, data):
        orig_name = PeopleBaseModel.orig_column_name(self, data)
        person = Person()
        person.unserialize(data)
        return get_new_name(person, orig_name)

    def new_column_father(self, data):
        return new_column_parent(self, data, data[0], data[2], "FATHER2", FamilyModel.orig_column_father)
    
    def new_column_mother(self, data):
        return new_column_parent(self, data, data[0], data[3], "MOTHER2", FamilyModel.orig_column_mother)
else:
    def new_column_name(self, data):
        orig_name = PeopleBaseModel.orig_column_name(self, data)
        return get_new_name(data, orig_name)

    def new_column_father(self, data):
        return new_column_parent(self, data, data.handle, data.father_handle, "FATHER2", FamilyModel.orig_column_father)
    
    def new_column_mother(self, data):
        return new_column_parent(self, data, data.handle, data.mother_handle, "MOTHER2", FamilyModel.orig_column_mother)
    
def new_column_parent(self, data, family_handle, parent_handle, cache_key, orig_func):
    if not parent_handle: return ""

    cached, value = self.get_cached_value(family_handle, cache_key)
    if cached: return value

    orig_name = orig_func(self, data)
    person = self.db.get_person_from_handle(parent_handle)
    new_name = get_new_name(person, orig_name)
    self.set_cached_value(family_handle, cache_key, new_name)
    return new_name
    
def get_new_name(person, orig_name):
    primary_surname = person.get_primary_name().get_surname()
    names = set()
    for n in person.get_alternate_names():
        sn = n.get_surname()
        if sn and sn != primary_surname:
            names.add(sn)
    if names:
        other_surnames = ", ".join(names)
        return f"{orig_name} ({other_surnames})"
    else:
        return orig_name




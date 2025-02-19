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

# Filter Progress
# ===============
# Adds "Cancel" button to the progress indicator for the Filter gramplet.
# 
# All code is in this file so this is not an actual addon.

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

from gramps.gen.filters._genericfilter import GenericFilter
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

def new_check_func(self, db, id_list, task, user=None, tupleind=None, tree=False):
    from gramps.gui.utils import ProgressMeter
    final_list = []
    if user:
        progress = ProgressMeter(_("Filter"), can_cancel=True)
        progress.set_pass(header="Applying  ...", total=self.get_number(db))
    if id_list is None:
        with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
            for handle, data in cursor:
                person = self.make_obj()
                person.unserialize(data)
                if user:
                    if progress.step():
                        #print("breaking3")
                        break
                if task(db, person) != self.invert:
                    final_list.append(handle)
    else:
        for data in id_list:
            if tupleind is None:
                handle = data
            else:
                handle = data[tupleind]
            person = self.find_from_handle(db, handle)
            if user:
                if progress.step():
                    #print("breaking4")
                    break
            if task(db, person) != self.invert:
                final_list.append(data)
    if user:
        progress.close()
    return final_list

def new_check_and(self, db, id_list, user=None, tupleind=None, tree=False):
    from gramps.gui.utils import ProgressMeter
    final_list = []
    flist = self.flist
    if user:
        progress = ProgressMeter(_("Filter"), can_cancel=True)
        progress.set_pass(header=_("Applying ..."), total=self.get_number(db))
    if id_list is None:
        with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
            for handle, data in cursor:
                person = self.make_obj()
                person.unserialize(data)
                if user:
                    if progress.step():
                        #print("breaking1")
                        break
                val = all(rule.apply(db, person) for rule in flist)
                if val != self.invert:
                    final_list.append(handle)
    else:
        for data in id_list:
            if tupleind is None:
                handle = data
            else:
                handle = data[tupleind]
            person = self.find_from_handle(db, handle)
            if user:
                if progress.step():
                    #print("breaking2")
                    break
            val = all(rule.apply(db, person) for rule in flist if person)
            if val != self.invert:
                final_list.append(data)
    if user:
        progress.close()
    return final_list
    
GenericFilter.check_func = new_check_func
GenericFilter.check_and = new_check_and


# Originals:
#    def check_func(self, db, id_list, task, user=None, tupleind=None, tree=False):
#        final_list = []
#        if user:
#            user.begin_progress(_("Filter"), _("Applying ..."), self.get_number(db))
#        if id_list is None:
#            with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
#                for handle, data in cursor:
#                    person = self.make_obj()
#                    person.unserialize(data)
#                    if user:
#                        user.step_progress()
#                    if task(db, person) != self.invert:
#                        final_list.append(handle)
#        else:
#            for data in id_list:
#                if tupleind is None:
#                    handle = data
#                else:
#                    handle = data[tupleind]
#                person = self.find_from_handle(db, handle)
#                if user:
#                    user.step_progress()
#                if task(db, person) != self.invert:
#                    final_list.append(data)
#        if user:
#            user.end_progress()
#        return final_list
#
#    def check_and(self, db, id_list, user=None, tupleind=None, tree=False):
#        final_list = []
#        flist = self.flist
#        if user:
#            user.begin_progress(_("Filter"), _("Applying ..."), self.get_number(db))
#        if id_list is None:
#            with self.get_tree_cursor(db) if tree else self.get_cursor(db) as cursor:
#                for handle, data in cursor:
#                    person = self.make_obj()
#                    person.unserialize(data)
#                    if user:
#                        user.step_progress()
#                    val = all(rule.apply(db, person) for rule in flist)
#                    if val != self.invert:
#                        final_list.append(handle)
#        else:
#            for data in id_list:
#                if tupleind is None:
#                    handle = data
#                else:
#                    handle = data[tupleind]
#                person = self.find_from_handle(db, handle)
#                if user:
#                    user.step_progress()
#                val = all(rule.apply(db, person) for rule in flist if person)
#                if val != self.invert:
#                    final_list.append(data)
#        if user:
#            user.end_progress()
#        return final_list
#        




# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Kari Kujansuu
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

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.plug.report.utils import find_spouse
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.datehandler import get_date
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gen.lib.eventtype import EventType

from gramps.gui.editors import EditPerson
from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gui.dialog import ErrorDialog
from gramps.gui.widgets import SimpleButton

_ = glocale.translation.gettext

class Children(Gramplet):
    """
    Displays the children of a person or family.
    """
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()
        self.uistate.connect('nameformat-changed', self.update)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.treeview = self.build_treeview()
        self.treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        #self.merge_button = Gtk.Button(_("Merge"))
        #self.merge_button.connect("clicked", self.merge_clicked)
        self.merge_button = SimpleButton("gramps-merge", self.merge_clicked)
        self.merge_button.set_sensitive(False)

        hbox.pack_start(self.merge_button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self.treeview, False, False, 0)
        vbox.show_all()
        self.treeview.get_selection().connect("changed", self.selection_changed)
        return vbox

    def merge_clicked(self, _widget):
        model, treepaths = self.treeview.get_selection().get_selected_rows()
        print(model)
        handles = []
        for treepath in treepaths:
            row = list(model[treepath])
            print(row)
            handles.append(row[0])
        if len(handles) != 2:
            ErrorDialog(_("Error"), _("Merge exactly two persons"))
            return
        from gramps.gui.merge import MergePerson
        MergePerson(self.dbstate, self.uistate, [], handles[0], handles[1])
            
    def selection_changed(self, _widget):
        model, treepaths = self.treeview.get_selection().get_selected_rows()
        self.merge_button.set_sensitive(len(treepaths) == 2)
    
            
    def get_date_place(self, event):
        """
        Return the date and place of the given event.
        """
        event_date = ''
        event_place = ''
        event_sort = '%012d' % 0
        if event:
            event_date = get_date(event)
            event_sort = '%012d' % event.get_date_object().get_sort_value()
            event_place = place_displayer.display_event(self.dbstate.db, event)
        return (event_date, event_sort, event_place)

    def edit_person(self, treeview):
        """
        Edit the selected child.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            try:
                person = self.dbstate.db.get_person_from_handle(handle)
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass

    def edit_person(self, treeview):
        """
        Edit the selected child.
        """
        model, treepaths = self.treeview.get_selection().get_selected_rows()
        handles = []
        for treepath in treepaths:
            row = list(model[treepath])
            handle = row[0]
            try:
                person = self.dbstate.db.get_person_from_handle(handle)
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            break

class PersonChildMerge(Children):
    """
    Displays the children of a person.
    """
    def build_treeview(self):
        """
        Build the GUI interface.
        """
        top = Gtk.TreeView()
        tip = _('Double-click on a row to edit the selected child.')
        #top.set_tooltip(tip)
        titles = [('', NOSORT, 50,),
                  (_('Child'), 1, 250),
                  (_('Birth Date'), 3, 100),
                  ('', 3, 100),
                  (_('Death Date'), 5, 100),
                  ('', 5, 100),
                  (_('Last event date'), 6, 120),
                  (_('Last event type'), 7, 120),
                  ]
        self.model = ListModel(top, titles, event_func=self.edit_person)
        return top

    def db_changed(self):
        self.connect(self.dbstate.db, 'person-update', self.update)

    def active_changed(self, handle):
        self.update()

    def main(self):
        active_handle = self.get_active('Person')
        self.model.clear()
        if active_handle:
            self.display_person(active_handle)
        else:
            self.set_has_data(False)

    def update_has_data(self):
        active_handle = self.get_active('Person')
        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def get_has_data(self, active_person):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_person is None:
            return False
        for family_handle in active_person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family and family.get_child_ref_list():
                return True
        return False

    def display_person(self, active_handle):
        """
        Display the children of the active person.
        """
        active_person = self.dbstate.db.get_person_from_handle(active_handle)
        for family_handle in active_person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            self.display_family(family, active_person)
        self.set_has_data(self.model.count > 0)

    def display_family(self, family, active_person):
        """
        Display the children of given family.
        """
        spouse_handle = find_spouse(active_person, family)
        if spouse_handle:
            spouse = self.dbstate.db.get_person_from_handle(spouse_handle)
        else:
            spouse = None

        for child_ref in family.get_child_ref_list():
            child = self.dbstate.db.get_person_from_handle(child_ref.ref)
            self.add_child(child, spouse)

    def add_child(self, child, spouse):
        """
        Add a child to the model.
        """
        name = name_displayer.display(child)
        if spouse:
            spouse = name_displayer.display(spouse)
        spouse = spouse or ''
        birth = get_birth_or_fallback(self.dbstate.db, child)
        birth_date, birth_sort, birth_place = self.get_date_place(birth)
        death = get_death_or_fallback(self.dbstate.db, child)
        death_date, death_sort, death_place = self.get_date_place(death)
        last_event_date = "1900-01-01"
        last_event_type = _("Death")
        last_event_date, last_event_type = self.find_last_event_for_person(child)
        self.model.add((child.get_handle(),
                        name,
                        birth_date,
                        birth_sort,
                        death_date,
                        death_sort,
                        last_event_date,
                        last_event_type,
                        ))

    
    def find_last_event(self, obj):
        # type: (Union[Person,Family]) -> Tuple[Optional[Date],str]
        lastdate = None
        lasttype = ""
        for eref in obj.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(eref.ref)
            eventtype = event.get_type()
            eventdate = event.get_date_object()
            role = eref.get_role()
            if eventdate is None: 
                continue
            if str(eventdate) == "0000-00-00":
                continue
            if role == EventRoleType.PRIMARY and eventtype == EventType.DEATH: 
                lastdate = eventdate
                lasttype = str(eventtype) + "/" + str(role)
                return lastdate, lasttype
            if role == EventRoleType.PRIMARY and eventtype == EventType.BURIAL: 
                continue
            if lastdate is None or eventdate > lastdate:
                lastdate = eventdate
                lasttype = str(eventtype) + "/" + str(role)
        return lastdate, lasttype
    
    def find_last_event_for_person(self, person):
        # type: (Person) -> Tuple[Optional[Date],str]
        lastdate, lasttype = self.find_last_event(person)
        for famhandle in person.get_family_handle_list():
            fam = self.dbstate.db.get_family_from_handle(famhandle)
            d2, t2 = self.find_last_event(fam)
            if d2 is not None and (lastdate is None or d2 > lastdate):
                lastdate = d2
                lasttype = t2
            for childref in fam.get_child_ref_list():
                child = self.dbstate.db.get_person_from_handle(childref.ref)
                birthref = child.get_birth_ref()
                if birthref is None: 
                    continue
                birth = self.dbstate.db.get_event_from_handle(birthref.ref)
                eventtype = birth.get_type()
                birthdate = birth.get_date_object()
                if birthdate is None: 
                    continue
                if lastdate is None or birthdate > lastdate:
                    lastdate = birthdate
                    lasttype = "Lapsen syntymä"
        if lastdate:
            return str(lastdate), str(lasttype)
        else:
            return None, ""


class FamilyChildMerge(Children):
    """
    Displays the children of a family.
    """
    def build_treeview(self):
        """
        Build the GUI interface.
        """
        tip = _('Double-click on a row to edit the selected child.')
        top = Gtk.TreeView()
        #top.set_tooltip(tip)
        titles = [('', NOSORT, 50,),
                  (_('Child'), 1, 250),
                  (_('Birth Date'), 3, 100),
                  ('', 3, 100),
                  (_('Birth Place'), 5, 100),
                  (_('Death Date'), 6, 100),
                  ('', 6, 100),
                  (_('Death Place'), 5, 100),
                  ]
        self.model = ListModel(top, titles, event_func=self.edit_person)
        return top

    def db_changed(self):
        self.connect(self.dbstate.db, 'family-update', self.update)
        self.connect_signal('Family', self.update)  # familiy active-changed
        self.connect(self.dbstate.db, 'person-update', self.update)

    def main(self):
        active_handle = self.get_active('Family')
        self.model.clear()
        if active_handle:
            family = self.dbstate.db.get_family_from_handle(active_handle)
            self.display_family(family)
        else:
            self.set_has_data(False)

    def update_has_data(self):
        active_handle = self.get_active('Family')
        if active_handle:
            active = self.dbstate.db.get_family_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def get_has_data(self, active_family):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_family is None:
            return False
        if active_family.get_child_ref_list():
            return True
        return False

    def display_family(self, family):
        """
        Display the children of given family.
        """
        for child_ref in family.get_child_ref_list():
            child = self.dbstate.db.get_person_from_handle(child_ref.ref)
            self.add_child(child)
        self.set_has_data(self.model.count > 0)

    def add_child(self, child):
        """
        Add a child to the model.
        """
        name = name_displayer.display(child)
        birth = get_birth_or_fallback(self.dbstate.db, child)
        birth_date, birth_sort, birth_place = self.get_date_place(birth)
        death = get_death_or_fallback(self.dbstate.db, child)
        death_date, death_sort, death_place = self.get_date_place(death)
        self.model.add((child.get_handle(),
                        name,
                        birth_date,
                        birth_sort,
                        birth_place,
                        death_date,
                        death_sort,
                        death_place,
                        ))

#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2023 Kari Kujansuu
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

import html
import traceback
from pprint import pprint

from gramps.gen.lib.eventtype import EventType

try: # imports used only for type hints
    from typing import Tuple, List, Union
    from gramps.gen.db import DbGeneric
    from gramps.gui.plug.quick._textbufdoc import TextBufDoc
except:
    pass

from gi.repository import Gtk

from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.errors import WindowActiveError

from gramps.gen.lib import Citation
from gramps.gen.lib import Event
from gramps.gen.lib import EventRef
from gramps.gen.lib import Family
from gramps.gen.lib import Note
from gramps.gen.lib import Person

from gramps.gui.dialog import ErrorDialog
from gramps.gui.dialog import OkDialog
from gramps.gui.selectors.selectorfactory import SelectorFactory
from gramps.gui.editors.editeventref import EditEventRef

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

from gramps.gen.config import config as configman

config = configman.register_manager("add-multiple-events")
config.register("defaults.event_type", "")
config.register("defaults.place", "")

def run(db, document, db_obj):
    # type: (DbGeneric, TextBufDoc, Union[Person,Family]) -> None
    try:
        obj = AddEvents(db, document, db_obj)
        ok = obj.run()
#         if not ok:
#             ErrorDialog(_("Error"), _("This quick view does not work in the Quick View gramplet"))
#             return
    except Exception as e:
        traceback.print_exc()
        OkDialog(_("Unexpected error"), str(e))


class AddEvents:
    def __init__(self, db, document, obj):
        # type: (DbGeneric, TextBufDoc, Union[Person,Family]) -> None
        self.db = db
        self.uistate = document.uistate
        self.dbstate = self.uistate.viewmanager.dbstate
        self.document = document
        self.obj = obj
        
#         o = document.text_view
#         while o:
#             print("---")
#             print(o)
#             #pprint(o.__dict__)
#             o = o.get_parent()
        
        config.load()
        self.default_event_type = config.get("defaults.event_type")

        self.default_place_handle = None
        place_gramps_id = config.get("defaults.place")
        if place_gramps_id:
            place = self.db.get_place_from_gramps_id(place_gramps_id)
            if place:
                self.default_place_handle = place.handle


    
    def xxxrun(self):
        # type: () -> None

        # If used as a regular Quick View:
        # - Destroy the default dialog.
        # - Find the window (dialog) that contains the document so that we can destroy it.
        # - See DisplayBuf.__init__ in gramps/gui/plug/quick/_textbufdoc.py
        #
        """
        This needs to work both 
            1) as a regular Quick View 
        or 
            2) invoked from the Quick View gramplet
        
        A regular Quick View creates a dialog that displays the results.
        We cannot use that dialog here because....???
        So that dialog is destroyed and we create a new dialog.
        
        The Quick View gramplet assumes that the Quick View 
        uses the TextView that is created by the gramplet. However, we want to 
        display arbitrary widgets and a TextView is not enough.
         
        """
        if self.is_regular_quick_view():
            pass
        text_view = self.document.text_view
        parent = text_view.get_parent()
        if isinstance(parent, Gtk.ScrolledWindow):
            scrolled_window = parent
            scrolled_window.remove(text_view)
            box = Gtk.VBox()
            scrolled_window.add(box)
            box.add(text_view)
        else:
            scrolled_window = parent.get_parent()
            box = scrolled_window.get_child()
        text_view.hide()
        vbox = scrolled_window.get_parent()
        dialog = vbox.get_parent()
        if isinstance(dialog, Gtk.Dialog):
            dialog.close()
            dialog.destroy()
            container = None
        else:
            container = box
        self.get_options(self.obj, container)

    def run(self):
        # type: () -> None

        # If used as a regular Quick View:
        # - Destroy the default dialog.
        # - Find the window (dialog) that contains the document so that we can destroy it.
        # - See DisplayBuf.__init__ in gramps/gui/plug/quick/_textbufdoc.py
        #
        """
        This needs to work both 
            1) as a regular Quick View 
        or 
            2) invoked from the Quick View gramplet
        
        A regular Quick View creates a dialog that displays the results.
        We cannot use that dialog here because....???
        So that dialog is destroyed and we create a new dialog.
        
        The Quick View gramplet assumes that the Quick View 
        uses the TextView that is created by the gramplet. However, we want to 
        display arbitrary widgets and a TextView is not enough.
        
        The Quick View gramplet also invokes the quick view repeatedly
        with the same TextView (stored in document.text_view). This TextView
        is the only way to find the ScrolledView that the gramplet uses 
        (the ScrolledView is the parent of the TextView).
        
        On the other hand we must remove the TextView from the ScrolledView 
        so that we can replace it with our own widget.
        
        The solution I found is to replace the TextView with a new VBox that contains
        both the original TextView and our new widget (also a VBox).

        Before_
            ScrolledView -> TextView

        After:
            ScrolledView -> VBox -> TextView
                                    Vbox (container)
        
        So when this code is called the first time the TextView parent is the ScrolledView. 
        We recognize this and create the new VBox and store the TextView in the VBox
        and the VBox in the ScrolledView.

        In subsequent calls we find that the parent of the TextView is not a ScrolledView
        but a VBox. Then the ScrolledView is the parent of the VBox and we can use the other
        widget in the VBox as our widget (container). Our widget must be inside the
        ScrolledView because otherwise it wouldn't be displayed in the gramplet.
         
        """
        self.document.text_view.hide() # in any case this should be hidden
        
        if self.is_regular_quick_view():
            dialog = self.get_regular_quick_view_dialog()
            dialog.close()
            dialog.destroy()
            self.get_options(self.obj)
        else:
            text_view = self.document.text_view
            parent = text_view.get_parent()
            if isinstance(parent, Gtk.ScrolledWindow):
                scrolled_window = parent
                scrolled_window.remove(text_view)
                box = Gtk.VBox()
                box.add(text_view)
                scrolled_window.add(box)
            else:
                scrolled_window = parent.get_parent()
                box = scrolled_window.get_child()
                old_container = box.get_children()[1]
                box.remove(old_container)
            container = Gtk.VBox()
            box.add(container)
            box.show()
            self.get_options(self.obj, container)

    def is_regular_quick_view(self):
        dialog = self.get_regular_quick_view_dialog()
        return isinstance(dialog, Gtk.Dialog)

    def get_regular_quick_view_dialog(self):
        text_view = self.document.text_view
        scrolled_window = text_view.get_parent()
        vbox = scrolled_window.get_parent()
        if vbox is None: return None
        dialog = vbox.get_parent()
        return dialog
        

    def add_events(self, _widget=None):
        affected_handles = [handle for (handle,checkbox) in self.checks if checkbox.get_active()]
        print("affected_handles",affected_handles)
        self.add_events2(self.selected_obj, affected_handles, self.selected_ref.role, self.checkbox_share.get_active())
        
    def add_events2(self, selected_obj, affected_handles, role, share):
        # type: () -> None
        with DbTxn(_("Adding events"), self.db) as self.trans:
            for person_handle in affected_handles:
                self.add_object_for_person(person_handle, selected_obj, role, share)
            if selected_obj.new_event and not share:
                self.db.remove_event(selected_obj.handle, self.trans)


    def get_birth_date(self, person):
        birth_ref = person.get_birth_ref()
        if not birth_ref: return None
        birth_event = self.db.get_event_from_handle(birth_ref.ref)
        if not birth_event: return None
        return birth_event.get_date_object()
    
    def get_death_date(self, person):
        death_ref = person.get_death_ref()
        if not death_ref: return None
        death_event = self.db.get_event_from_handle(death_ref.ref)
        if not death_event: return None
        return death_event.get_date_object()
    
    def add_object_for_person(self, person_handle, selected_obj, role, share):
        # type: (str, Event) -> None
        person = self.db.get_person_from_handle(person_handle)
        if share:
            event = selected_obj
        else:
            event = Event(selected_obj)
            event.handle = None
            event.gramps_id = None
            if event.type == EventType.RESIDENCE and event.date.is_compound():
                birth_date = self.get_birth_date(person)
                death_date = self.get_death_date(person)
                if birth_date and event.date < birth_date:
                    event.date.set_yr_mon_day(*birth_date.get_ymd(),remove_stop_date=False)
                if death_date and event.date > death_date:
                    event.date.set2_yr_mon_day(*death_date.get_ymd())
                
                
            self.db.add_event(event, self.trans)
        eref = EventRef()
        eref.ref = event.handle
        eref.role = role
        person.add_event_ref(eref)
        self.db.commit_person(person, self.trans)


    def get_options(self, obj, container=None):
        # type: (Union[Person,Family]) -> None

        """
        This will either display a dialog (regular Quick View)
        or add the same content to the container so it will be displayed
        within the Quick View gramplet.
        """        
        if not container:
            dialog = Gtk.Dialog(modal=False)
    
            dialog.set_title(_("Add multiple events"))
            c = dialog.get_content_area()
            c.set_spacing(8)
        else:
            c = container
        lbl1 = Gtk.Label()
        lbl1.set_markup("<b>" + _("Add a copy of the selected event to:") + "</b>")
        lbl1.set_halign(Gtk.Align.START)

        lbl2 = Gtk.Label()
        lbl2.set_markup("<b>" + _("Selected event:") + "</b>")
        lbl2.set_halign(Gtk.Align.START)

        self.lbl_source = Gtk.Label()
        self.lbl_source.set_halign(Gtk.Align.START)
        self.lbl_source.set_margin_top(10)
        self.lbl_source.set_margin_bottom(10)

        self.event_frame = Gtk.Frame()
        self.event_frame.add(Gtk.Label("None"))

        self.role_label = Gtk.Label()
        self.role_label.set_halign(Gtk.Align.START)

        self.checkbox_share = Gtk.CheckButton(_("Share event"))

        editbutton = Gtk.Button(_("Select Event"))
        editbutton.connect("clicked", self.selectevent)

        addbutton = Gtk.Button(_("New Event"))
        addbutton.connect("clicked", self.newevent)

        btnbox = Gtk.ButtonBox()
        btnbox.add(editbutton)
        btnbox.add(addbutton)

        self.grid = Gtk.Grid()
        self.grid.rownum = 0
        grid = self.grid

        c.pack_start(btnbox, False, False, 0)
        c.pack_start(lbl2, False, False, 0)
        c.pack_start(self.event_frame, False, False, 0)
        c.pack_start(self.role_label, False, False, 0)
        c.pack_start(self.checkbox_share, False, False, 0)
        c.pack_start(lbl1, False, False, 0)
        c.pack_start(grid, False, False, 0)
        c.set_size_request(300, -1)

        self.checks = []  # type: List[Tuple[str, Gtk.CheckButton]]

        if isinstance(obj, Family):
            self.add_checkbutton("Father", obj.get_father_handle())
            self.add_checkbutton("Mother", obj.get_mother_handle())
            for childref in obj.get_child_ref_list():
                self.add_checkbutton("Child", childref.ref)

        if isinstance(obj, Person):
            self.add_checkbutton("", obj.handle)

            for parent_family_handle in obj.get_parent_family_handle_list():
                family = self.db.get_family_from_handle(parent_family_handle)

                self.add_spacer()
                self.add_checkbutton("Father", family.father_handle)
                self.add_checkbutton("Mother", family.mother_handle)
#                 for childref in family.get_child_ref_list():
#                     self.add_checkbutton("> Sibling", childref.ref)

            for parent_family_handle in obj.get_family_handle_list():
                family = self.db.get_family_from_handle(parent_family_handle)
                spouse_handle = family.mother_handle if family.father_handle == obj.handle else family.father_handle
                self.add_spacer()
                if spouse_handle:
                    self.add_checkbutton("Spouse", spouse_handle)
                for childref in family.get_child_ref_list():
                    self.add_checkbutton("Child", childref.ref)

        self.add_spacer()
        check_all = self.make_checkbutton("check/clear all", "")
        self.grid.attach(check_all, 0, self.grid.rownum, 1, 1)
        self.grid.rownum += 1
        check_all.connect("clicked", self.check_all_changed)

        if not container:
            self.ok_button = dialog.add_button(_("OK"), 1)
            self.cancel_button = dialog.add_button(_("Cancel"), 0)
            dialog.show_all()
            dialog.connect("response", self.handle_response)
        else:
            self.ok_button = Gtk.Button(_("Add events"))
            self.ok_button.connect("clicked", self.add_events)
            btnbox2 = Gtk.ButtonBox()
            btnbox2.pack_start(self.ok_button, False, False, 0)
            c.pack_start(btnbox2, False, False, 0)
            c.show_all()
            #c.show_all()
        self.ok_button.set_sensitive(False)

    def handle_response(self, dialog, rspcode):
        # type: (Gtk.Dialog, int) -> None
        if rspcode == 1:
            self.add_events()
        dialog.destroy()


    def add_event_to_dialog(self, eventref, event):
        # type: (EventRef, Event) -> None
        participants = ", ".join(self.get_participants(event.handle))
        f = self.event_frame
        f.remove(f.get_child())
        g = Gtk.Grid()
        f.add(g)
        g.rownum = 0
        self.add_row(g, "ID", event.gramps_id)
        self.add_row(g, "Type", event.type)
        self.add_row(g, "Description", event.description)
        self.add_row(g, "Date", event.date)
        self.add_row(g, "Place", place_displayer.display_event(self.db, event))
        self.add_row(g, "Participants", participants)

        g.set_column_spacing(5)
        g.show_all()

        self.role_label.set_text("Role: " + str(eventref.role))
        self.selected_ref = eventref
        self.selected_obj = event

        self.default_event_type = event.type.xml_str() 
        config.set("defaults.event_type", self.default_event_type)

        if event.place:
            self.default_place_handle = event.place
            place = self.db.get_place_from_handle(event.place)
            config.set("defaults.place", place.gramps_id)
        
        config.save()

        self.ok_button.set_sensitive(True)

    def get_participants(self, handle):
        # type: (str) -> List[str]
        namelist = []
        for class_name, referrer_handle in self.db.find_backlink_handles(
            handle, ["Person", "Family"]
        ):
            # role = self.get_role_of_eventref(self.db, referrer_handle, self.handle)
            if class_name == "Family":
                family = self.db.get_family_from_handle(referrer_handle)
                if family.father_handle:
                    person = self.db.get_person_from_handle(family.father_handle)
                    name = name_displayer.display(person)
                    namelist.append(name)
                if family.mother_handle:
                    person = self.db.get_person_from_handle(family.mother_handle)
                    name = name_displayer.display(person)
                    namelist.append(name)
            if class_name == "Person":
                person = self.db.get_person_from_handle(referrer_handle)
                name = name_displayer.display(person)
                namelist.append(name)
        return namelist

    def add_row(self, grid, *cols):
        # type: (Gtk.Grid, str) -> None
        for colnum, col in enumerate(cols):
            value = str(col)
            if colnum == 0:
                value = _(value)
            lbl = Gtk.Label(value)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_line_wrap(True)
            grid.attach(lbl, colnum, grid.rownum, 1, 1)
        grid.rownum += 1


    def selectevent(self, _widget):
        # type: (Gtk.Widget) -> None
        SelectEvent = SelectorFactory('Event')

        sel = SelectEvent(self.dbstate, self.uistate, [])
        event = sel.run()
        if event:
            try:
                event.new_event = False
                ref = EventRef()
                EditEventRef(
                    self.dbstate, self.uistate, [],
                    event, ref, self.eventref_callback)
            except WindowActiveError:
                from gramps.gui.dialog import WarningDialog
                WarningDialog(_("Cannot share this reference"),
                              "",
                              parent=self.uistate.window)

    def newevent(self, _widget):
        # type: (Gtk.Widget) -> None
        try:
            ref = EventRef()
            event = Event()
            event.new_event = True
            if self.default_event_type:
                event.type.set_from_xml_str(self.default_event_type)
            if self.default_place_handle:
                event.set_place_handle(self.default_place_handle)
            EditEventRef(
                self.dbstate, self.uistate, [],
                event, ref, self.eventref_callback)
        except WindowActiveError:
            from gramps.gui.dialog import WarningDialog
            WarningDialog(_("Cannot share this reference"),
                          "",
                          parent=self.uistate.window)


    def eventref_callback(self, eventref, event):
        # type: (EventRef, Event) -> None
        self.add_event_to_dialog(eventref, event)

    def check_all_changed(self, *args):
        # type: (Gtk.CheckButton) -> None
        active = args[0].get_active()
        for _, check in self.checks:
            check.set_active(active)

    def add_checkbutton(self, title, handle):
        # type: (str, str) -> None
        if handle is None:
            return
        name = self.get_name(handle)
        check = self.make_checkbutton(title, name)
        self.checks.append((handle, check))
        self.grid.attach(check, 0, self.grid.rownum, 1, 1)
        self.grid.rownum += 1

    def add_spacer(self):
        # type: () -> None
        self.grid.attach(Gtk.Label(""), 0, self.grid.rownum, 1, 1)
        self.grid.rownum += 1


    def make_checkbutton(self, title, name):
        # type: (str, str) -> Gtk.CheckButton
        lbl = Gtk.Label()
        title = _(title)
        name = html.escape(name)
        lbl.set_markup(title + " <b>" + name + "</b>")
        check = Gtk.CheckButton()
        check.add(lbl)
        check.set_margin_top(5)
        check.set_active(True)
        return check

    def get_name(self, person_handle):
        # type: (str) -> str
        if person_handle:
            person = self.db.get_person_from_handle(person_handle)
            return name_displayer.display(person)
        else:
            return ""

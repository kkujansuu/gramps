# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
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

#
# Person gramplet to display events and associated citations as well as citations
# attached directly to a person. Allows citations to be dragged and dropped to attach them
# to other events. Citation references can also be removed (using a right click
# to open a context menu.
#
# Modified from gramps/plugins/gramplet/events.py
# Drag-and-drop and context menu code modified from embeddedlist.py.
# Kari Kujansuu 2022
#

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import pickle
from pprint import pprint

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk, Gdk
# Gtk.TreeViewDropPosition

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.editors import EditEvent, EditCitation, EditPerson
from gramps.gui.listmodel import ListModel, NOSORT, INTEGER
from gramps.gen.plug import Gramplet
from gramps.gen.plug.report.utils import find_spouse
from gramps.gui.dbguielement import DbGUIElement
from gui.display import display_url
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import get_date
from gramps.gen.utils.db import (get_participant_from_event,
                                 get_birth_or_fallback,
                                 get_marriage_or_fallback)
from gramps.gen.db import DbTxn
from gramps.gen.errors import WindowActiveError, HandleError
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import OkDialog, QuestionDialog, QuestionDialog2
from gramps.gen.merge.mergeeventquery import MergeEventQuery
from gramps.gen.lib.date import Date
_ = glocale.translation.gettext

from gramps.gui.editors.displaytabs import CitationEmbedList
from gramps.gui.ddtargets import DdTargets

age_precision = config.get('preferences.age-display-precision')

class Events_and_Citations(Gramplet, DbGUIElement):


    
    
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)
        DbGUIElement.__init__(self, self.dbstate.db)
        self.popup_menu_items = [
            (True, "Open link", self.open_link),
            (True, "Delete", self.delete_citation),
        ]
        self.main()

    """
    Displays the events for a person or family.
    """
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()



    def _connect_db_signals(self):
        """
        called on init of DbGUIElement, connect to db as required.
        """
        self.callman.register_callbacks({'event-update': self.changed})
        self.callman.connect_all(keys=['event'])

    def changed(self, handle):
        """
        Called when a registered event is updated.
        """
        self.update()
        self.main() # allows this to work also in an editor window (not as gramplet)

    def right_click(self, obj, event):
        # from embeddedlist.py
        """
        On right click show a popup menu.
        This is populated with get_popup_menu_items
        """
        # print("right_click",obj,event)

        """
        Select the row at the current cursor position.
        
        """
        tree = self.model.tree
        wx, wy = tree.convert_bin_window_to_widget_coords(event.x, event.y)
        row = tree.get_dest_row_at_pos(wx, wy)
        if row:
            tree.get_selection().select_path(row[0])


        
        self.__store_menu = Gtk.Menu() #need to keep reference or menu disappears
        menu = self.__store_menu
        menu.set_reserve_toggle_size(False)

        (model, treeiter) = self.model.tree.get_selection().get_selected()
        if treeiter:
            row = model[treeiter]
            url = row[-2]
            # print(url)
            index = 0 if url else 1        
        for (need_write, title, func) in self.popup_menu_items[index:]:
            item = Gtk.MenuItem.new_with_mnemonic(title)
            item.connect('activate', func)
            if need_write and self.dbstate.db.readonly:
                item.set_sensitive(False)
            item.show()
            menu.append(item)
        menu.popup(None, None, None, None, event.button, event.time)
        return True

    def delete_citation(self, menuitem):
        (model, treeiter) = self.model.tree.get_selection().get_selected()
        if treeiter:
            citation_handle = model[treeiter][1]
            parent_iter = model.iter_parent(treeiter)
            if parent_iter is not None:
                parent_row = model[parent_iter][:]
                parent_handle = parent_row[1]
                # print("parent_handle",parent_handle)
                if self.dbstate.db.has_event_handle(parent_handle):
                    parent = self.dbstate.db.get_event_from_handle(parent_handle)
                    commitfunc = self.dbstate.db.commit_event
                elif self.dbstate.db.has_person_handle(parent_handle):
                    parent = self.dbstate.db.get_person_from_handle(parent_handle)
                    commitfunc = self.dbstate.db.commit_person
                else:
                    return
                citation = self.dbstate.db.get_citation_from_handle(citation_handle)
                # print(parent)
                # print(citation)
                with DbTxn("Removing citation", self.dbstate.db) as trans:
                    parent.remove_citation_references([citation_handle])
                    commitfunc(parent, trans)
            else: # no parent, i.e. Person or Event row, allow deletion of events
                event_handle = model[treeiter][1]
                if self.dbstate.db.has_event_handle(event_handle):
                    event = self.dbstate.db.get_event_from_handle(event_handle)
                    active_handle = self.get_active('Person')
                    person = self.dbstate.db.get_person_from_handle(active_handle)
                    if person:
                        newrefs = []
                        for eref in person.get_event_ref_list():
                            if eref.ref != event_handle:
                                newrefs.append(eref)
                        person.set_event_ref_list(newrefs)
                        with DbTxn("Removing event", self.dbstate.db) as trans:
                            self.dbstate.db.commit_person(person, trans)
                        
    def open_link(self, menuitem):
        (model, treeiter) = self.model.tree.get_selection().get_selected()
        if treeiter:
            row = model[treeiter]
            url = row[-2]
            # print(url)
            display_url(url)
                                
    
    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _('Double-click on a row to edit the selected event.')
        self.set_tooltip(tip)
        top = Gtk.TreeView()
        titles = [
                  ('', NOSORT, 50,),        # row type (person, event, citation)
                  ('', NOSORT, 50,),        # handle
                  (_('Type'), 2, 100),      # event type
#                  (_('Link'), NOSORT, 20),       # has url
                  (_('Description'), 3, 400),   # event description or citation title+page
                  (_('Date'), 5, 100),      # event data
                  ('', NOSORT, 50),
                  (_('Place'), 6, 300),
                  (_('Role'), 7, 100),
                  (_('URL'), 8, 100),
                  
        ]
        self.model = ListModel(top, titles, event_func=self.edit_event, 
                               right_click=self.right_click,
                               list_mode="tree")
        self.set_draggable_source(top)
        self.set_draggable_dest(top)
        #top.connect("click", lambda *args: print("clicked",args))
        return top

    def add_event_ref(self, event_ref, node=None):
        """
        Add an event to the model.
        """
        if node is None:
            self.callman.register_handles({'event': [event_ref.ref]})
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            event_date = get_date(event)
            event_sort = '%012d' % event.get_date_object().get_sort_value()
            person_age = self.column_age(event)
            person_age_sort = self.column_sort_age(event)
            place = place_displayer.display_event(self.dbstate.db, event)

            participants = get_participant_from_event(self.dbstate.db,
                                                      event_ref.ref)

            #num_citations = len(event.get_citation_list())
            
            node = self.model.add([
                            "event",
                            event.get_handle(),
                            str(event.get_type()),    
#                            "", # has link
                            event.get_description(), 
                            event_date,              
                            event_sort,              
                            place,                   
                            str(event_ref.get_role()),
                            "",         # url
                        ])
            obj = event
        else:
            obj = event_ref

        for citation_handle in obj.get_citation_list():
            citation = self.dbstate.db.get_citation_from_handle(citation_handle)
            page = citation.get_page()
            if not page:
                page = _('<No Citation>')
            source_handle = citation.get_reference_handle()
            source = self.dbstate.db.get_source_from_handle(source_handle)
            title = source.get_title()
            author = source.get_author()
            publisher = source.get_publication_info()
            citation_text = self.get_citation_text(citation)
            text = ""
            if citation.page.find("http") >= 0:
                text = citation.page
            elif len(citation.note_list) > 0:
                note_handle = citation.note_list[0]
                note = self.dbstate.db.get_note_from_handle(note_handle)
                text = note.get()
#            if text.startswith("Kansallisarkisto: "):
#                text = text.split()[1]
#            if text.startswith("SSHY: "):
#                text = text.split()[1]
#            if text.startswith("Kansalliskirjasto: "):
#                text = text.split()[1]
            if text.startswith("http"):
                url = text
                if url: url = url.split()[0]
            else:
                url = ""
            i = text.find("http")
            if i >= 0:
                url = text[i:].split()[0]
            else:
                url = ""
            has_link = "\U0001F517" if url else " "
            #print("citation --------->",[citation_handle,"",citation_text] + [""]*4)
            if citation.date.is_empty():
                citation_date = ""
            else:
                citation_date = str(citation.date)
            self.model.add([
                "citation",
                citation_handle,
                has_link, 
                citation_text,
                citation_date,
                "",
                "",
                "",
                url,
            ], 
            node=node)

    def format_event(self, event):
        event_type = str(event.get_type())
        event_date = get_date(event)
        place = place_displayer.display_event(self.dbstate.db, event)
        return "{id}: {type} {date} {place}".format(id=event.gramps_id,type=event_type, date=event_date, place=place)

    def get_citation_text(self, citation):
        source_handle = citation.get_reference_handle()
        source = self.dbstate.db.get_source_from_handle(source_handle)
        title = source.get_title()
        author = source.get_author()
        publisher = source.get_publication_info()
        return title + ": " + citation.page

    def column_age(self, event):
        """
        Returns a string representation of age in years.  Change
        precision=2 for "year, month", or precision=3 for "year,
        month, days"
        """
        date = event.get_date_object()
        start_date = self.cached_start_date
        if date and start_date:
            return (date - start_date).format(precision=age_precision)
        else:
            return ""

    def column_sort_age(self, event):
        """
        Returns a string version of number of days of age.
        """
        date = event.get_date_object()
        start_date = self.cached_start_date
        if date and start_date:
            return "%09d" % int(date - start_date)
        else:
            return ""

    def edit_event(self, treeview):
        """
        Edit the selected event.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 1)
            try:
                if self.dbstate.db.has_event_handle(handle):
                    event = self.dbstate.db.get_event_from_handle(handle)
                    EditEvent(self.dbstate, self.uistate, [], event)
                    return
                if self.dbstate.db.has_citation_handle(handle):
                    citation = self.dbstate.db.get_citation_from_handle(handle)
                    EditCitation(self.dbstate, self.uistate, [], citation)
                    return
                if self.dbstate.db.has_person_handle(handle):
                    person = self.dbstate.db.get_person_from_handle(handle)
                    EditPerson(self.dbstate, self.uistate, [], person)
                    return
            except WindowActiveError:
                pass

    def set_draggable_source(self, widget):
        dnd_types = [DdTargets.CITATION_LINK.target()]
        mask = Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.CONTROL_MASK
        widget.enable_model_drag_source(mask, dnd_types, Gdk.DragAction.COPY)
        #widget.drag_source_set_target_list(None)
        #widget.drag_source_add_text_targets()
        widget.connect("drag-data-get", self.drag_data_get)

    def set_draggable_dest(self, widget):
        
        dnd_types = [DdTargets.CITATION_LINK.target()]

        widget.enable_model_drag_dest(dnd_types, Gdk.DragAction.COPY)
        #widget.enable_model_drag_dest(DdTargets._all_gramps_types, Gdk.DragAction.COPY)
        #widget.enable_model_drag_dest([], Gdk.DragAction.COPY)

        #widget.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        #widget.drag_dest_set_target_list(None)
        widget.drag_dest_add_text_targets()

                
        widget.connect("drag-data-received", self.drag_data_received)

    def drag_data_get(self, widget, drag_context, sel_data, info, time):
        # print("drag_data_get", sel_data)
        selection = widget.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            row = model[treeiter][:]
            handle = row[1]      
            if self.dbstate.db.has_person_handle(handle):
                return # cannot drag the person
            if self.dbstate.db.has_event_handle(handle):
                event = self.dbstate.db.get_event_from_handle(handle)
                value = (DdTargets.EVENT.drag_type, id(widget), handle, 0)
                link = DdTargets.EVENT
            if self.dbstate.db.has_citation_handle(handle):
                citation = self.dbstate.db.get_citation_from_handle(handle)
                value = (DdTargets.CITATION_LINK.drag_type, id(widget), handle, 0)
                link = DdTargets.CITATION_LINK

            data = pickle.dumps(value)
            # pass as a string (8 bits)
            sel_data.set(link.atom_drag_type, 8, data)
        
        
        
    def drag_data_received(self, widget, drag_context, x, y, data, info, time):
        d = data.get_data()
        # print("drag_data_received", d)
        if not d: return
        data = pickle.loads(d)
        if isinstance(data, list):
            data = [pickle.loads(x) for x in data]
        else:
            data = [data]
        # print("== data:", data) # data: [('citation-link', 140046182367296, 'e95cb710ed55842be78345fa8bf', 0)]

        rowtype = data[0][0]
        handle = data[0][2]
        if self.dbstate.db.has_event_handle(handle):
            event_handle = handle
        if self.dbstate.db.has_citation_handle(handle):
            citation_handle = handle
            citation = self.dbstate.db.get_citation_from_handle(citation_handle)
        if not rowtype in (
            DdTargets.CITATION_LINK.drag_type,
            DdTargets.EVENT.drag_type,
        ):
            return
        
        selection = widget.get_selection()
        model, treeiter = selection.get_selected()
        dest_path_and_pos = widget.get_dest_row_at_pos(x, y)
        if dest_path_and_pos is None: return
        dest_path, dest_pos = widget.get_dest_row_at_pos(x, y)
        if dest_path:
            selected_iter = widget.get_model().get_iter(dest_path)
            row = model[selected_iter][:]
            # print(" row", row)

            if rowtype == DdTargets.EVENT.drag_type: 
                event_handle2 = row[1]
                if event_handle == event_handle2:
                    return # should not merge to itself
                event1 = self.dbstate.db.get_event_from_handle(event_handle)
                event2 = self.dbstate.db.get_event_from_handle(event_handle2)
                ok_to_merge = QuestionDialog2("Merge events",
                    "Merge events\n- {}\n- {}".format(self.format_event(event1), self.format_event(event2)),
                    "Ok to merge","Cancel").run()
                if ok_to_merge:
                    # print("merging...")
                    date1 = event1.get_date_object()
                    date2 = event2.get_date_object()
                    newdate = self.merge_date_ranges(date1, date2)
                    event1.set_date_object(newdate)
                    q = MergeEventQuery(self.dbstate, event1, event2)
                    q.execute()
                return
            
            new_row  = [
                "citation",
                citation_handle,
                "",
                self.get_citation_text(citation)] + [""]*5  # miksi tässä pitää olla 9 alkiota?

            #print(" new_row", new_row, len(new_row))
            x = dest_path.get_indices()
            if len(x) > 1:
                parent_index = int(x[0])
                child_index = int(x[1])
                parent_iter = self.model.model.iter_parent(selected_iter)
            else:
                parent_iter = selected_iter
                                
            parent_row = model[parent_iter][:]
            parent_handle = parent_row[1]

            if self.dbstate.db.has_event_handle(parent_handle):
                parent = self.dbstate.db.get_event_from_handle(parent_handle)
                commitfunc = self.dbstate.db.commit_event
            elif self.dbstate.db.has_person_handle(parent_handle):
                parent = self.dbstate.db.get_person_from_handle(parent_handle)
                commitfunc = self.dbstate.db.commit_person
            else:
                xxx

            with DbTxn("Adding citation", self.dbstate.db) as trans:
                if len(x) > 1:
                    citlist = parent.get_citation_list()
                    citlist.insert(x[1]+1, citation_handle)
                    citlist = parent.set_citation_list(citlist)
                else:
                    parent.add_citation(citation_handle)
                commitfunc(parent, trans)
        else:
            #print("append")
            pass
        return
    

    def merge_date_ranges(self, date1, date2):
        if date1.get_ymd() == (0, 0, 0): return date2
        if date2.get_ymd() == (0, 0, 0): return date1
        low1 = date1.get_ymd()
        low2 = date2.get_ymd()
        hi1 = date1.get_stop_ymd()
        hi2 = date2.get_stop_ymd()
        if hi1 == (0,0,0): hi1 = low1
        if hi2 == (0,0,0): hi2 = low2
        newlow = min(low1, low2)
        newhi = max(hi1, hi2)
        newdate = Date()
        newdate.set(modifier=Date.MOD_SPAN, value=[newlow[2], newlow[1], newlow[0], False, newhi[2], newhi[1], newhi[0], False])
        return newdate
    
class Person_Events_and_Citations(Events_and_Citations):
    """
    Displays the events for a person.
    """
    def db_changed(self):
        self.connect(self.dbstate.db, 'person-update', self.update)
        #self.connect(self.dbstate.db, 'person-update', self.main)

    def active_changed(self, handle):
        self.update()

    def update_has_data(self):
        active_handle = self.get_active('Person')
        active = None
        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))

    def get_has_data(self, active_person):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_person:
            if active_person.get_event_ref_list():
                return True
            for family_handle in active_person.get_family_handle_list():
                family = self.dbstate.db.get_family_from_handle(family_handle)
                if family:
                    for event_ref in family.get_event_ref_list():
                        return True
        return False

    def main(self): # return false finishes
        active_handle = self.get_active('Person')
        #print("active", active_handle)
        self.model.clear()
        self.callman.unregister_all()
        if active_handle:
            self.display_person(active_handle)
        else:
            self.set_has_data(False)

    def display_person(self, active_handle):
        """
        Display the events for the active person.
        """
        active_person = self.dbstate.db.get_person_from_handle(active_handle)
        if active_person:
            node = self.model.add([
                            "person",
                            active_handle,    # handle
                            _("Person"),             # "type"
#                            "",                      # has link
                            _(""),                   # description
                            "",                      # date
                            "",                      # date sort
                            "",                      # place
                            "",                      # role
                            "",                      # url
                        ])  
            self.add_event_ref(active_person, node=node)


            self.cached_start_date = self.get_start_date()
            for event_ref in active_person.get_event_ref_list():
                self.add_event_ref(event_ref)
            for family_handle in active_person.get_family_handle_list():
                family = self.dbstate.db.get_family_from_handle(family_handle)
                #self.display_family(family, active_person) # ei oteta perhetapahtumia vielä mukaan
        else:
            self.cached_start_date = None
        self.set_has_data(self.model.count > 0)
        self.model.tree.expand_all()

    def display_family(self, family, active_person):
        """
        Display the events for the given family.
        """
        spouse_handle = find_spouse(active_person, family)
        if spouse_handle:
            spouse = self.dbstate.db.get_person_from_handle(spouse_handle)
        else:
            spouse = None
        if family:
            for event_ref in family.get_event_ref_list():
                self.add_event_ref(event_ref, spouse)

    def get_start_date(self):
        """
        Get the start date for a person, usually a birth date, or
        something close to birth.
        """
        active_handle = self.get_active('Person')
        active = self.dbstate.db.get_person_from_handle(active_handle)
        event = get_birth_or_fallback(self.dbstate.db, active)
        return event.get_date_object() if event else None


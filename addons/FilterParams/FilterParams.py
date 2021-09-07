#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021      Gramps developers, Kari Kujansuu

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

import os
import re
import traceback
from collections import defaultdict
from pprint import pprint

try:
    from typing import List, Tuple, Optional, Iterator, Generator, Any, Callable
except:
    pass
 
from gi.repository import Gtk, Gdk, GObject

from gramps.gen.lib import Person
from gramps.gen.utils.callman import CallbackManager

from gramps.gui.editors import EditPerson
from gramps.gui.dbguielement import DbGUIElement
from gramps.gui.glade import Glade
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool
from gramps.gui.views.listview import ListView
from gramps.gui.user import User

from gramps.gen.const import CUSTOM_FILTERS
from gramps.gen.datehandler import displayer
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.errors import FilterError
from gramps.gen.filters import reload_custom_filters 
import gramps.gen.filters 

from gramps.gen.utils.string import conf_strings
from gramps.gui.widgets import DateEntry

from gramps.gui.editors.filtereditor import MyPlaces, MyInteger, MyLesserEqualGreater
from gramps.gui.editors.filtereditor import MyID, MySource, MyFilters
from gramps.gui.editors.filtereditor import MySelect, MyBoolean, MyList
from gramps.gui.editors.filtereditor import MyEntry, ShowResults
from gramps.gui.editors.filtereditor import _name2typeclass
from gramps.gui.editors.filtereditor import EditFilter

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


regex_tip = _('Interpret the contents of string fields as regular '
        'expressions.\n'
        'A decimal point will match any character. '
        'A question mark will match zero or one occurences '
        'of the previous character or group. '
        'An asterisk will match zero or more occurences. '
        'A plus sign will match one or more occurences. '
        'Use parentheses to group expressions. '
        'Specify alternatives using a vertical bar. '
        'A caret will match the start of a line. '
        'A dollar sign will match the end of a line.')

#-------------------------------------------------------------------------
#
# Tool
#
#-------------------------------------------------------------------------
class Tool(tool.Tool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (Any, Any, Any, str, Callable) -> None
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.user = user
        self.uistate = user.uistate
        self.dbstate = dbstate
        self.track = []
        #self.filterdb = FilterList(CUSTOM_FILTERS)
        #self.filterdb.load()
        self.frame = None
        self.categories = [
            "Person",
            "Family",
            "Event",
            "Place",
            "Citation",
            "Source",
            "Repository",
            "Media",
            "Note",
        ]
        self.categories_translated = [_(cat) for cat in self.categories]
        self.colors = [
             Gdk.RGBA(0.9,0.9,0.99, 0.999),
             Gdk.RGBA(0.9,0.99,0.9, 0.999),
             Gdk.RGBA(0.99,0.99,0.9, 0.999),
             Gdk.RGBA(0.99,0.9,0.9, 0.999),
             Gdk.RGBA(0.9,0.99,0.99, 0.999),
             Gdk.RGBA(0.99,0.9,0.99, 0.999),
        ]
        self.use_colors = True

        self.dialog = self.create_gui()

    def populate_filters(self, category):
        self.filterdb = gramps.gen.filters.CustomFilters
        self.filterdb.load()
        filters = self.filterdb.get_filters_dict(category)
        self.filternames = []
        for filter in filters.values():
            self.filternames.append(filter.get_name())
        self.filter_combo.widget.get_model().clear()
        self.filter_combo.fill_combo(self.filternames)
        if len(self.filternames) > 0: 
            self.filter_combo.widget.set_active(0)
        
    def create_gui(self):
        self.filternames = []
        category = self.uistate.viewmanager.active_page.get_category()         
        if category == "People": category = "Person"
        if category.endswith("ies"): category = category[0:-3] + "y"
        if category.endswith("s"): category = category[0:-1]
        self.current_category = category    

        dialog = Gtk.Dialog(title=_("Filter parameters"), parent=self.uistate.window)

        hdr = Gtk.Label()
        hdr.set_markup("<b>" + _("Select a filter") + "</b>")
        dialog.vbox.pack_start(hdr, False, False, 5)

        self.execute_button = dialog.add_button(_("Test run"), Gtk.ResponseType.OK)
        self.execute_button.set_sensitive(False)
        self.execute_button.connect("clicked", self.execute_clicked)
        self.execute_button.set_tooltip_text(_("Runs the filter - the parameters are not saved permanently"))

        self.update_button = dialog.add_button(_("Save"), Gtk.ResponseType.OK)
        self.update_button.set_sensitive(False)
        self.update_button.connect("clicked", self.update_clicked)
        self.update_button.set_tooltip_text(_("Saves the changes permanently"))

        close_button = dialog.add_button(_("Close"), Gtk.ResponseType.CANCEL)
        close_button.connect("clicked", self.close_clicked)
        close_button.set_tooltip_text(_("Close the window - any changes are lost if you did not save"))
        
        self.filter_combo = self.MyCombo([])
        category_combo = self.MyCombo(list(zip(self.categories, self.categories_translated)))

        hbox = Gtk.HBox()
        lbl = Gtk.Label(_("Category") + ":")
        hbox.pack_start(lbl, False, False, 5)
        hbox.pack_start(category_combo.widget, False, False, 5)
        dialog.vbox.pack_start(hbox, False, False, 5)
        
        hbox = Gtk.HBox()
        lbl = Gtk.Label(_("Filter") + ":")
        hbox.pack_start(lbl, False, False, 5)
        hbox.pack_start(self.filter_combo.widget, False, False, 5)
        dialog.vbox.pack_start(hbox, False, False, 5)

        self.box = Gtk.Box()
        self.dialog = dialog
        dialog.vbox.pack_start(self.box, False, False, 5)

        self.filter_combo.widget.connect("changed", self.on_filter_changed)
        category_combo.widget.connect("changed", self.on_category_changed)
        if self.current_category not in self.categories:
            self.current_category = "Person"
            
        category_combo.set_value(self.current_category)
        dialog.connect("delete-event", lambda x, y: self.close_clicked(dialog))
        dialog.show_all()
        return dialog

    def on_category_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is None: return
        model = combo.get_model()
        cat_name_translated = model[tree_iter][0]
        i = self.categories_translated.index(cat_name_translated)
        self.current_category = self.categories[i]
        if self.frame:
            self.frame.destroy()
            self.frame = None
        self.execute_button.set_sensitive(False)
        self.update_button.set_sensitive(False)
        self.populate_filters(self.current_category)

    def get_color(self, level):
        return self.colors[level % len(self.colors)]

    def get_all_handles(self, category):
        # method copied from gramps/gui/editors/filtereditor.py
        # Why use iter for some and get for others?
        if category == 'Person':
            return self.db.iter_person_handles()
        elif category == 'Family':
            return self.db.iter_family_handles()
        elif category == 'Event':
            return self.db.get_event_handles()
        elif category == 'Source':
            return self.db.get_source_handles()
        elif category == 'Citation':
            return self.db.get_citation_handles()
        elif category == 'Place':
            return self.db.iter_place_handles()
        elif category == 'Media':
            return self.db.get_media_handles()
        elif category == 'Repository':
            return self.db.get_repository_handles()
        elif category == 'Note':
            return self.db.get_note_handles()       
         
    def execute_clicked(self, _widget):
        class User2:
            """
            Helper class to provide "can_cancel" functionality to 
            the progress indicator used by gramps.gen.filters._genericfilter.GenericFilter.apply().
            Replaces the gramps.gui.user.User class for this case.
            Code copied from gramps/gui/user.py.
            """
            def __init__(self, user):
                self.parent = user.parent
                self.uistate = user.uistate
                self.parent = user.parent
            def begin_progress(self, title, message, steps):
                # Parameter "can_cancel" added to ProgressMeter creation.
                from gramps.gui.utils import ProgressMeter
                self._progress = ProgressMeter(title, parent=self.parent, can_cancel=True)
                if steps > 0:
                    self._progress.set_pass(message, steps, ProgressMeter.MODE_FRACTION)
                else:
                    self._progress.set_pass(message, mode=ProgressMeter.MODE_ACTIVITY)
            def step_progress(self):
                res = self._progress.step()
                if res:
                    self.end_progress()
                    raise StopIteration
            def end_progress(self):
                self._progress.close()
                self._progress = None

        user = User2(self.user)

        # code copied from gramps/gui/editors/filtereditor.py (test_clicked)
        try:
            self.update_params()
            filter = self.getfilter(self.current_category, self.current_filtername)
            handle_list = filter.apply(self.db, self.get_all_handles(self.current_category), user=user)
        except StopIteration:
            return
        except FilterError as msg:
            (msg1, msg2) = msg.messages()
            ErrorDialog(msg1, msg2, parent=self.window)
            return
        ShowResults(self.db, self.uistate, self.track, handle_list,
                    self.current_filtername,self.current_category)

    # methods copied from gramps/gui/editors/filtereditor.py
    def add_new_filter(self, obj):
        the_filter = GenericFilterFactory(self.current_category)()
        EditFilter(self.current_category, self.dbstate, self.uistate, self.track,
                   the_filter, self.filterdb, update=None)

    def edit_filter(self, obj):
        store, node = self.clist.get_selected()
        if node:
            gfilter = self.clist.get_object(node)
            EditFilter(self.namespace, self.dbstate, self.uistate, self.track,
                       gfilter, self.filterdb, self.draw_filters)

    def clone_filter(self, obj):
        store, node = self.clist.get_selected()
        if node:
            old_filter = self.clist.get_object(node)
            the_filter = GenericFilterFactory(self.namespace)(old_filter)
            the_filter.set_name('')
            EditFilter(self.namespace, self.dbstate, self.uistate, self.track,
                       the_filter, self.filterdb, self.draw_filters)

        
    def update_clicked(self, _widget):
        #self.update_params()
        self.filterdb.save()

    def close_clicked(self, _widget):
        #print("FilterParams closing")
        reload_custom_filters()  # so that our (non-saved) changes will be discared
        self.dialog.destroy()
        self.dialog = None
    
    def get_widgets(self,arglist,filtername):
        # Code copied from gramps/gui/editors/filtereditor.py
        pos = 0
        tlist = []
        for v in arglist:
            if isinstance(v, tuple):
                # allows filter to create its own GUI element
                l = Gtk.Label(label=v[0], halign=Gtk.Align.END)
            else:
                l = Gtk.Label(label=v, halign=Gtk.Align.END)
            l.show()
            if v == _('Place:'):
                t = MyPlaces([])
            elif v in [_('Reference count:'),
                        _('Number of instances:')
                        ]:
                t = MyInteger(0, 999)
            elif v == _('Reference count must be:'):
                t = MyLesserEqualGreater()
            elif v == _('Number must be:'):
                t = MyLesserEqualGreater(2)
            elif v == _('Number of generations:'):
                t = MyInteger(1, 32)
            elif v == _('ID:'):
                t = MyID(self.dbstate, self.uistate, self.track,
                         self.namespace)
            elif v == _('Source ID:'):
                t = MySource(self.dbstate, self.uistate, self.track)
            elif v == _('Filter name:'):
                t = MyFilters(self.filterdb.get_filters(self.namespace),
                              filtername)
            # filters of another namespace, name may be same as caller!
            elif v == _('Person filter name:'):
                t = MyFilters(self.filterdb.get_filters('Person'))
            elif v == _('Event filter name:'):
                t = MyFilters(self.filterdb.get_filters('Event'))
            elif v == _('Source filter name:'):
                t = MyFilters(self.filterdb.get_filters('Source'))
            elif v == _('Repository filter name:'):
                t = MyFilters(self.filterdb.get_filters('Repository'))
            elif v == _('Place filter name:'):
                t = MyFilters(self.filterdb.get_filters('Place'))
            elif v in _name2typeclass:
                additional = None
                if v in (_('Event type:'), _('Personal event:'),
                         _('Family event:')):
                    additional = self.db.get_event_types()
                elif v == _('Personal attribute:'):
                    additional = self.db.get_person_attribute_types()
                elif v == _('Family attribute:'):
                    additional = self.db.get_family_attribute_types()
                elif v == _('Event attribute:'):
                    additional = self.db.get_event_attribute_types()
                elif v == _('Media attribute:'):
                    additional = self.db.get_media_attribute_types()
                elif v == _('Relationship type:'):
                    additional = self.db.get_family_relation_types()
                elif v == _('Note type:'):
                    additional = self.db.get_note_types()
                elif v == _('Name type:'):
                    additional = self.db.get_name_types()
                elif v == _('Surname origin type:'):
                    additional = self.db.get_origin_types()
                elif v == _('Place type:'):
                    additional = sorted(self.db.get_place_types(),
                                        key=lambda s: s.lower())
                t = MySelect(_name2typeclass[v], additional)
            elif v == _('Inclusive:'):
                t = MyBoolean(_('Include selected Gramps ID'))
            elif v == _('Case sensitive:'):
                t = MyBoolean(_('Use exact case of letters'))
            elif v == _('Regular-Expression matching:'):
                t = MyBoolean(_('Use regular expression'))
            elif v == _('Include Family events:'):
                t = MyBoolean(_('Also family events where person is spouse'))
            elif v == _('Primary Role:'):
                t = MyBoolean(_('Only include primary participants'))
            elif v == _('Tag:'):
                taglist = ['']
                taglist = taglist + [tag.get_name() for tag in self.dbstate.db.iter_tags()]
                t = MyList(taglist, taglist)
            elif v == _('Confidence level:'):
                t = MyList(list(map(str, list(range(5)))),
                           [_(conf_strings[i]) for i in range(5)])
            elif v == _('Date:'):
                t = DateEntry(self.uistate, self.track)
            elif v == _('Day of Week:'):
                long_days = displayer.long_days
                days_of_week = long_days[2:] + long_days[1:2]
                t = MyList(list(map(str, range(7))), days_of_week)
            elif v == _('Units:'):
                t = MyList([0, 1, 2],
                           [_('kilometers'), _('miles'), _('degrees')])
            elif isinstance(v, tuple):
                # allow filter to create its own GUI element
                t = v[1](self.db)
            else:
                t = MyEntry()
            t.set_hexpand(True)
            tlist.append(t)
            pos += 1
        return tlist[0]

    class MyGrid(Gtk.Grid):
        """
        Gtk.Grid that is easier to use; just call .add() to add a new item.
        Set argument 'incrow' to False if next item should be on the same row.
        """
        def __init__(self):                       
            Gtk.Grid.__init__(self)
            self.set_margin_left(10)
            self.set_margin_top(0)
            self.set_margin_right(10)
            self.set_margin_bottom(10)
            self.row = 0
            self.col = 0
        def add(self, widget, incrow=True):
            self.attach(widget,self.col,self.row,1,1)
            if incrow: 
                self.row += 1
                self.col = 0
            else:
                self.col += 1

    def update_params(self, *args):
        for (filter,invert_checkbox,logical_combo) in self.filterparams:
            filter.set_invert(invert_checkbox.get_active())
            filter.set_logical_op(self.ops[logical_combo.widget.get_active()])
        
        for (rule, paramindex, entry) in self.entries:
            value = str(entry.get_text()) 
            rule.list[paramindex] = value
        for (rule,use_regex) in self.regexes:
            value = use_regex.get_active()
            rule.use_regex = value
        for oldvalue, entries in self.values.items():
            value = None
            for entry,rule,paramindex in entries:
                if value is None: 
                    value = entry.get_text()
                else:
                    rule.list[paramindex] = value
                entry.set_text(value)
                
        #self.filterdb.save()
        #reload_custom_filters()

    def getfilter(self, category, filtername):
        #filters = self.filterdb.get_filters_dict(category)
        filters = self.filterdb.get_filters_dict(category)
        return filters.get(filtername)

           
    def addfilter(self, grid, category, filtername, level):
        """
        Add the GUI widgets for the filter in the supplied Gtk.Grid.
        The grid is already contained in a Gtk.Frame with appropriate label.
        
        Saves the widget in three arrays (entries, filterparams and regexes).
        """
        if level > 10: return
        filter = self.getfilter(category, filtername)
        if filter is None:  # not found for some reason 
            lbl = Gtk.Label()
            lbl.set_halign(Gtk.Align.START)
            lbl.set_markup("<span color='red' size='larger'>" + _("Error") +"</span>")
            grid.add(lbl)
            return 
        if filter.comment:
            # grid.parent is the frame
            grid.get_parent().set_tooltip_text(filter.comment)

        clsname = filter.__class__.__name__

        invert_checkbox = Gtk.CheckButton("invert")
        invert_checkbox.set_active(filter.get_invert())
        invert_checkbox.set_tooltip_text(_("Return values that do not match the filter rules")) 

        choices = [
            _("All rules must apply"),
            _("At least one rule must apply"),
            _("Exactly one rule must apply"),
        ]
        self.ops = ["and","or","one"]
        op = filter.get_logical_op()
        combo = self.MyCombo(choices)        
        combo.widget.set_active(self.ops.index(op))
        hbox = Gtk.HBox()
        hbox.add(invert_checkbox)
        if len(filter.get_rules()) > 1:
            hbox.add(combo.widget)
        grid.add(hbox)

        self.filterparams.append((filter,invert_checkbox, combo))
        
        for rule in filter.get_rules():
            lab = Gtk.Label(" ") # to separate the frames
            grid.add(lab)

            clsname = rule.__class__.__name__
            lbl = Gtk.Label(str(level) + ". " + clsname)
            lbl.set_halign(Gtk.Align.START)

            # First check if this rule uses another filter.
            # This heuristic check might not work if the rule is not using the usual conventions
            if (len(rule.labels) == 1 and rule.labels[0] == _("Filter name:") or
                clsname.startswith("Matches") and clsname.endswith("Filter")):
                if clsname.startswith("Matches") and clsname.endswith("Filter"):
                    matchcategory = clsname.replace("Matches","").replace("Filter","")
                    if matchcategory == "":
                        matchcategory = category
                else:
                    matchcategory = category
                filtername = rule.list[0]
                grid2 = self.add_frame(grid, level, "<b>"+clsname+"</b>: " + filtername)
               
                self.addfilter(grid2, matchcategory, filtername, level+1)
                continue

            # Regular rule
            grid2 = self.add_frame(grid, level, "<b>"+clsname+"</b>",
                                   tooltip=_(rule.name) + "\n\n" + _(rule.description))
            for paramindex,(caption, value) in enumerate(zip(rule.labels,rule.list)):
                if type(caption) is tuple:
                    caption = caption[0]
                lbl = Gtk.Label(caption)
                lbl.set_halign(Gtk.Align.END)
                lbl.set_margin_left(10)
                grid2.add(lbl, False)
                self.namespace = category
                entry = self.get_widgets([caption], filtername)
                entry.set_text(value)
                self.entries.append((rule,paramindex,entry))
                grid2.add(entry)
                if caption == _('ID:'): # link ID fields if they have the same value
                    if value in self.values:
                        entry.set_sensitive(False)
                    self.values[value].append((entry,rule,paramindex))
                    entry.entry.connect("changed", self.update_params)

            if rule.allow_regex:
                use_regex = Gtk.CheckButton(label=_('Use regular expressions'))
                use_regex.set_tooltip_text(regex_tip)
                use_regex.set_active(rule.use_regex)
                grid2.add(use_regex)
                self.regexes.append((rule,use_regex))
    
    def add_frame(self, grid, level, caption, tooltip=None):
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_markup(caption)
        frame2 = Gtk.Frame()
        frame2.set_label_widget(lbl)
        if self.use_colors:
            frame2.override_background_color(Gtk.StateFlags.NORMAL, self.get_color(level))
        
        grid.add(frame2)
        grid2 = self.MyGrid()
        frame2.add(grid2) #
        frame2.set_tooltip_text(tooltip) 
        return grid2
    
    def on_filter_changed(self, combo):
#         import random
#         random.shuffle(self.colors)
        tree_iter = combo.get_active_iter()
        if tree_iter is None: return
        model = combo.get_model()
        try:
            filtername = model[tree_iter][0]
        except:
            traceback.print_exc()
            return

        # load from xml file, any temporary changes are lost
        reload_custom_filters()
        self.filterdb = gramps.gen.filters.CustomFilters        

        self.current_filtername = filtername
        if self.frame:
            self.frame.destroy()
        self.grid = self.MyGrid()
        self.entries = []
        self.filterparams = []
        self.regexes = []
        self.values = defaultdict(list)
        
        lbl = Gtk.Label(filtername)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_markup("<b>"+filtername+"</b>")

        frame2 = Gtk.Frame()
        frame2.set_label_widget(lbl)
        if self.use_colors:
            frame2.override_background_color(Gtk.StateFlags.NORMAL, self.get_color(0))
        frame2.add(self.grid)

        self.addfilter(self.grid, self.current_category, filtername, 1)
        self.box.add(frame2)
        self.frame = frame2
        self.dialog.resize(1,1) # shrink to minimum size needed    
        self.dialog.show_all()
        self.execute_button.set_sensitive(True)
        self.update_button.set_sensitive(True)

    class MyWidget:
        def __init__(self, widget):
            # type: (Gtk.Widget) -> None
            self.widget = widget
        def set_value(self, text):
            # type: (Any) -> None
            self.widget.set_text(text)
        def get_value(self):
            # type: () -> Any
            return self.widget.get_text()

                                    
    class MyCheckBox(MyWidget):
        def __init__(self):
            # type: () -> None
            self.widget = Gtk.CheckButton()
        def set_value(self, value):
            # type: (bool) -> None
            self.widget.set_active(value)
        def get_value(self):
            # type: () -> bool
            return self.widget.get_active()

    class MySpin(MyWidget):
        def __init__(self):
            # type: () -> None
            self.widget = Gtk.SpinButton()
            self.widget.set_numeric(True)
            adjustment = Gtk.Adjustment(upper=100, step_increment=1, page_increment=10)
            self.widget.set_adjustment(adjustment)            
        def set_value(self, value):
            # type: (int) -> None
            self.widget.set_value(value)
        def get_value(self):
            # type: () -> int
            return self.widget.get_value_as_int()

    class MyCombo():
        def __init__(self, entries, *, has_entry=False):
            # type: (List[str], bool) -> None
            #Gtk.ComboBoxText.__init__(self)
            self.entries = entries
            if len(entries) > 0 and type(entries[0]) == tuple:
                self.keys = [e[0] for e in entries]
                self.entries = [e[1] for e in entries]
            else:
                self.keys = self.entries
            if has_entry:
                self.widget = Gtk.ComboBoxText.new_with_entry()
            else:
                self.widget = Gtk.ComboBoxText()
                self.widget.set_entry_text_column(0)
            self.fill_combo(self.entries)

        def fill_combo(self, data_list, wrap_width=1):
            # type: (Gtk.ComboBox, List[str], int) -> None
            for data in data_list:
                if data:
                    if type(data) == tuple:
                        self.widget.append(data[0],data[1])
                        self.widget.set_id_column(0)
                        self.widget.set_entry_text_column(1)
                    else:
                        self.widget.append_text(data)
                        self.widget.set_entry_text_column(0)
    
            self.widget.set_popup_fixed_width(False)
            self.widget.set_wrap_width(wrap_width)

        def set_value(self, value):
            # type: (str) -> None
            if value in self.keys:
                i = self.keys.index(value)
            else:
                i = -1
            self.widget.set_active(i)
        def get_value(self):
            # type: () -> str
            return self.widget.get_active_text()


#------------------------------------------------------------------------
#
# Options
#
#------------------------------------------------------------------------
class Options(tool.ToolOptions):
    """
    Define options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        self.options_dict = dict(
        )
        self.options_help = dict(
        )


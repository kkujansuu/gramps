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

try:
    from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union
except:
    pass

import itertools
import json
import os
import random
import sys
import time
import traceback

from collections import defaultdict
#from dataclasses import dataclass
from pprint import pprint

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject

from gramps.gen.config import config as configman
from gramps.gen.db import DbTxn
from gramps.gen.dbstate import DbState
from gramps.gen.lib.baseobj import BaseObject
from gramps.gen.lib import Note, Person, Place
from gramps.gen.user import User

from gramps.gui.dialog import OkDialog, QuestionDialog2, ErrorDialog
from gramps.gui.editors.editperson import EditPerson
from gramps.gui.editors.editplace import EditPlace
from gramps.gui.plug import tool
from gramps.gui.glade import Glade

from supertool_utils import supertool_execute, get_context 

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class EndDialog(Gtk.Dialog):
    def __init__(self, msg):
        # type: (str) -> None
        super().__init__(title=_("End of Game"))
        self.set_default_size(150, 100)
        label = Gtk.Label(label=msg)
        box = self.get_content_area()
        box.add(label)
        self.add_button(_("New game"), 1)
        self.add_button(_("Quit"), 99)
        self.show_all()

RESPCODE_CHOOSE = 10
MAXRETRIES = 50
NUMRANDOMITEMS = 10

config = configman.register_manager("do-you-know-your-family")
config.register("defaults.num_questions_alternatives", "5,10,15,20,25")
config.register("defaults.num_choices_alternatives", "4,5,6")
config.register("defaults.num_questions", 10)
config.register("defaults.num_choices", 4)
config.register("defaults.selected", "")


#@dataclass
class Q:
    def __init__(self, question, choices, correct, keeporder=False):
        # type: (str, List[Tuple[str,Optional[BaseObject]]], int, bool) -> None
        self.question = question
        self.choices = choices
        self.correct = correct
        self.keeporder = keeporder

editfuncs = {
    "Person": EditPerson,
    "Place": EditPlace,
    }

#------------------------------------------------------------------------
#
# Tool
#
#------------------------------------------------------------------------
class Tool(tool.Tool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (DbState, User, Any, str, Callable) -> None
        self.user = user
        self.dbstate = dbstate
        self.uistate = user.uistate
        self.db = self.dbstate.db
        tool.Tool.__init__(self, dbstate, options_class, name)
        if self.db.get_number_of_people() < NUMRANDOMITEMS:
            ErrorDialog(_("The database is too small"), _("Need at least {} individuals.").format(NUMRANDOMITEMS))
            return

        glade = Glade("DoYouKnowYourFamily.glade")
        header = glade.get_object("header")
        box1 = glade.get_object("num_questions")
        box2 = glade.get_object("num_choices")
        questions_header = glade.get_object("questions_header")
        box3a = glade.get_object("questions1")
        box3b = glade.get_object("questions2")
        
        config.load()
        config_selected = config.get("defaults.selected")
        num_choices_alternatives = config.get("defaults.num_choices_alternatives")  # "4,5,6"
        num_questions_alternatives = config.get("defaults.num_questions_alternatives")
        numquestions = config.get("defaults.num_questions")
        numchoices = config.get("defaults.num_choices")

        confdialog = glade.toplevel
        self.set_font(confdialog)
        confdialog.set_title(_("Do You Know Your Family"))
        
        box1.set_margin_left(10)
        box1.set_margin_right(0)

        lbl1 = Gtk.Label()
        lbl1.set_markup("<b>" + _("Number of Questions") + "</b>")
        lbl1.set_halign(Gtk.Align.START)
        box1.pack_start(lbl1, False, False, 0)

        questions_alternatives = eval(num_questions_alternatives)
        questions_buttons = []
        but = None
        for n in questions_alternatives:
            but = Gtk.RadioButton.new_with_label_from_widget(but, str(n))
            box1.pack_start(but, False, False, 0)
            questions_buttons.append((but,n))
            but.set_active(n == numquestions)
            
        box2.set_margin_left(20)
        box2.set_margin_right(20)
        lbl2 = Gtk.Label()
        lbl2.set_markup("<b>" + _("Number of Choices") + "</b>")
        lbl2.set_halign(Gtk.Align.START)
        box2.pack_start(lbl2, False, False, 0)

        choices = eval(num_choices_alternatives)
        print(repr(choices))
        choice_buttons = []
        but = None
        for choice in choices:
            but = Gtk.RadioButton.new_with_label_from_widget(but, str(choice))
            box2.pack_start(but, False, False, 0)
            choice_buttons.append((but,choice))
            but.set_active(choice == numchoices)


        selected_methods = config_selected.split(",")
        box3 = Gtk.VBox()
        lbl3 = Gtk.Label()
        box4 = Gtk.VBox()
        #box3a = Gtk.VBox()

        lbl3.set_markup("<b>" + _("Questions") + "</b>")
        lbl3.set_halign(Gtk.Align.START)
        questions_header.pack_start(lbl3, False, False, 0)
        self.qlist = []
        cb_all = Gtk.CheckButton(_("select all"))
        questions_header.pack_start(cb_all, False, False, 50)

        self.button_start = confdialog.add_button(_("Start"), 1)

        cb_all.connect("toggled", self.select_all)
        cb_all.set_active(True)
        box = box3a
        n = 0
        for name, question in self.get_methods():
            if question.endswith("?"): question = question[0:-1]
            cb = Gtk.CheckButton(question.format("X", "Y"))
            if config_selected == "" or name in selected_methods:
                cb.set_active(True)
            box.add(cb)
            cb.connect("toggled", self.check_methods)
            self.qlist.append((name,cb))
            n += 1
            if n >= 10: # second column
                box = box3b


        box = Gtk.HBox()
        sw = Gtk.ScrolledWindow()
        sw.set_size_request(400, 600)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)

        box3.add(sw)
        sw.add(box3b)
        
        box.add(box1)
        box.add(box2)
        box.add(box3)

        header.set_markup("<b>" + _("Game that asks random questions about your family tree") + "</b>")
        header.set_margin_top(20)
        header.set_margin_bottom(20)

        confdialog.show_all()
        rsp = confdialog.run()
        confdialog.destroy()
        if rsp == -4: return

        for but,n in questions_buttons:
            if  but.get_active():
                self.numquestions = n
                
        for but,choice in choice_buttons:
            if  but.get_active():
                self.numchoices = choice

        self.selected = set()
        selected_methods = []
        for name, cb in self.qlist:
            if cb.get_active():
                self.selected.add(name)
                selected_methods.append(name)

        config.set("defaults.num_questions", self.numquestions)
        config.set("defaults.num_choices", self.numchoices)
        config.set("defaults.selected", ",".join(selected_methods))
        config.save()

        self.questions = Questions(self.dbstate, numchoices=self.numchoices, numrandomitems=NUMRANDOMITEMS)

        self.d = Gtk.Dialog()
        self.set_font(self.d)

        self.d.set_title(_("Do You Know Your Family"))
        self.but = self.d.add_button(_("Choose"), RESPCODE_CHOOSE )
        self.d.set_default_response(RESPCODE_CHOOSE)
        self.d.connect("response", self.handle_response)

        self.box = Gtk.VBox()
        self.d.get_content_area().add(self.box)
        self.box2 = None
        self.count = 0
        self.num_correct_answers = 0
        self.refresh_methods()
        self.next()

    def set_font(self, widget):
        # type: (Gtk.Widget) -> None
        css = b"* {font-size:16px}"
        p = Gtk.CssProvider()
        try:
            p.load_from_data(css)
            widget.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except:
            pass

    def check_methods(self, _widget):
        # type: (Gtk.Widget) -> None
        for name, cb in self.qlist:
            if cb.get_active():
                self.button_start.set_sensitive(True)
                return
        self.button_start.set_sensitive(False)
        

    def select_all(self, cb_all):
        # type: (Gtk.CheckButton) -> None
        for name, cb in self.qlist:
            cb.set_active(cb_all.get_active())

    def get_methods(self):
        # type: () -> Iterable[Tuple[str,str]]
        methods = Questions.__dict__.items()
        for (name,method) in methods:
            if not name.startswith("q_"):
                continue
            question = method.__defaults__[0]
            yield name, question

    def refresh_methods(self):
        # type: () -> None
        methods = Questions.__dict__.keys()
        #print(methods)
        self.methods = [m for m in methods if m in self.selected]


    def next(self):
        # type: () -> None
        if self.count == self.numquestions:
            msg = _("Correct answers: {}/{}").format(self.num_correct_answers, self.numquestions)
            d = EndDialog(msg)
            self.set_font(d)
            rsp = d.run()
            d.destroy()
            if rsp == 99: # quit
                self.d.destroy()
                return

            # start a new game
            self.refresh_methods()
            self.count = 0
            self.num_correct_answers = 0

        for i in range(MAXRETRIES):
            if len(self.methods) == 0:
                self.refresh_methods()
            m = random.choice(self.methods)
            method = getattr(self.questions, m)
            try:
                q = method()
                q.name = m
            except StopIteration:
                return
            except:
                traceback.print_exc()
                q = None
            if q:
                self.ask(q)
                self.methods.remove(m)
                return
            self.methods.remove(m)
        ErrorDialog(_("Error"), _("Unable to continue"))


    def ask(self, q):
        # type: (Q) -> None

        self.current_question = q
        grid = Gtk.Grid()
        if self.box:
            self.d.get_content_area().remove(self.box)

        box = Gtk.VBox()
        box.set_margin_left(20)
        box.set_margin_right(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        self.count += 1
        seq = "{}/{}".format(self.count, self.numquestions)
        lbl = Gtk.Label()
        lbl.set_markup("<b>" + seq + " " + q.question.replace("&","&amp;") + "</b>")
        lbl.set_margin_bottom(10)
        box.add(lbl)

        self.choicelist = Gtk.ListBox()
        if type(q.choices[0]) != tuple:
            q.choices = list(itertools.zip_longest(q.choices,[]))
        if not q.keeporder:
            random.shuffle(q.choices)

        for i, choice in enumerate(q.choices, start=1):
            lbl = Gtk.Label(choice[0])
            lbl.set_halign(Gtk.Align.START)
            self.choicelist.add(lbl)
        box.add(self.choicelist)

        self.but.set_sensitive(False)

        self.choicelist.connect("row-selected", lambda _,row: self.but.set_sensitive(True))
        self.choicelist.connect("button-press-event", self.button_press)
        first_row = self.choicelist.get_row_at_index(0)
        self.choicelist.select_row(first_row)

        self.d.get_content_area().add(box)
        self.result = Gtk.Label()
        self.result.set_margin_top(10)
        box.add(self.result)

        self.box2 = box
        self.box = box

        self.but.set_label(_("Choose"))
        self.show_result = True
        self.d.show_all()

    def button_press(self, treeview, event):
        # type: (Gtk.ListView, Gtk.Event) -> None
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
            proxyobj = self.current_question.choices[self.choicelist.get_selected_row().get_index()][1]
            if proxyobj is not None:
                editfuncs[proxyobj.namespace](self.dbstate, self.uistate, [], proxyobj.obj)




    def handle_response(self, dialog, rspcode):
        # type: (Gtk.Dialog, int) -> None
        self.user_dialog = None
        if rspcode == RESPCODE_CHOOSE:
            if self.show_result:
                selected = self.current_question.choices[self.choicelist.get_selected_row().get_index()][0]
                if selected == str(self.current_question.correct):
                    self.num_correct_answers += 1
                    self.result.set_text(_("Correct!"))
                else:
                    self.result.set_text(_("Incorrect\nCorrect choice is: {}").format(self.current_question.correct))
                self.but.set_label(_("Next"))
                self.show_result = False
            else:
                self.next()
            return
        #print(_("Unknown response type: ") + str(rspcode))



def current_year():
    # type: () -> int
    return time.localtime(time.time()).tm_year

class Base:
    q_123 = 1
    def __init__(self, dbstate, numchoices=4, numrandomitems=10):
        # type: (DbState, int, int) -> None
        self.dbstate = dbstate
        self.db = dbstate.db
        self.numchoices = numchoices
        self.numrandomitems = numrandomitems
        self.all_handles= {} # type: Dict[str,str]

    def loadhandles(self, category_name):
        # type: (str) -> None
        if category_name not in self.all_handles:
            category = get_context(self.db, category_name)
            self.all_handles[category_name] = category.get_all_objects_func()

    def randomhandle(self, category_name):
        # type: (str) -> str
        self.loadhandles(category_name)
        h = random.choice(self.all_handles[category_name])
        return h

    def randomhandles(self, category_name, numrandomitems=None):
        # type: (str, int) -> List[str]
        if numrandomitems is None:
            numrandomitems = self.numrandomitems
        self.loadhandles(category_name)
        h = random.sample(self.all_handles[category_name], numrandomitems)
        return h

    def randomplaceobjects(self, excluded, numchoices):
        # type: (List[Place], int) -> List[Place]
        "returns 'numchoices' random PlaceProxy objects"
        excluded_gramps_ids = [p.gramps_id for p in excluded]
        places = [] # type: List[Place]
        retries = 0
        while len(places) < numchoices:
            handles = self.randomhandles("Places")
            retries += 1
            if retries > MAXRETRIES:
                raise RuntimeError(_("Not found"))
            try:
                result = supertool_execute(dbstate=self.dbstate, category= "Places", handles=handles,
                      filter="name",
                      expressions="self",
                      ).rows
                for row in result:
                    place = row[0]
                    if place.gramps_id not in excluded_gramps_ids:
                        places.append(place)
                        excluded_gramps_ids.append(place.gramps_id)
                        if len(places) == numchoices:
                            return places
            except:
                retries += 1
                if retries > MAXRETRIES:
                    raise
                    raise RuntimeError(_("Not found"))
        return places


    def randompeopleobjects(self, excluded, numchoices, gender=None):
        # type: (List[Person], int, str) -> List[Person]
        retries = 0
        filter = "name"
        excluded_gramps_ids = [p.gramps_id for p in excluded]
        if gender:
            if gender not in ('M','F','U'):
                raise RuntimeError(_("Invalid gender: ") + gender)
            filter += " and gender == '{}'".format(gender)
        #print(filter)
        persons = [] # type: List[Person]
        while len(persons) < numchoices:
            retries += 1
            if retries > 20:
                raise RuntimeError(_("Not found"))
            handles = self.randomhandles("People")
            try:
                result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                      filter=filter,
                      expressions="self",
                      ).rows
                for row in result:
                    p = row[0]
                    if p.gramps_id not in excluded_gramps_ids:
                        persons.append(p)
                        excluded_gramps_ids.append(p.gramps_id)
                        if len(persons) == numchoices:
                            return persons
            except:
                retries += 1
                if retries > MAXRETRIES:
                    raise
                    raise RuntimeError(_("Not found"))
        return persons

    def randomoccupations(self, excluded, numchoices, gender=None):
        # type: (List[str], int, Optional[str]) -> List[str]
        results = [] # type: List[str]
        retries = 0
        while len(results) < numchoices:
            retries += 1
            if retries > 20:
                raise RuntimeError(_("Not found"))
            handles = self.randomhandles("Events")
            try:
                result = supertool_execute(dbstate=self.dbstate, category= "Events", handles=handles,
                      filter="type == 'Occupation'",
                      expressions="description",
                      ).rows
                for row in result:
                    occup = row[0]
                    if occup not in results + excluded:
                        results.append(occup)
                        if len(results) == numchoices:
                            return results
            except:
                retries += 1
                if retries > MAXRETRIES:
                    raise
                    raise RuntimeError(_("Not found"))
        return results

    def randomyears(self, year):
        # type: (int) -> List[str]
        """
        Return a sorted list of random years, the given yearis included
        """
        yearrange = list(range(1600, current_year()+1))
        yearrange.remove(year)
        years = random.sample(yearrange, self.numchoices-1)
        #print("years",years)
        years.append(year)
        #random.shuffle(years)
        years.sort()
        #print(years)
        return [str(y) for y in years]

def pname(p):
    return p.obj.get_primary_name().get_regular_name()

class Questions(Base):

    def q_birthyear(self, question = _("When was {} born?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                  filter="surname",
                  expressions="self,str(birth.date),str(death.date),death.date.obj-birth.date.obj",
                  ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            year = row[1][0:4]
            if not year.isdigit(): return None
            year = int(year)
            if year == 0: return None
            choices = self.randomyears(year)
            return Q(question.format(name),
                [(year,None) for year in choices],
                year,
                keeporder=True)
        return None

    def q_deathyear(self, question = _("When did {} die?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                  filter="surname",
                  expressions="self,str(birth.date),str(death.date),death.date.obj-birth.date.obj",
                  ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            year = row[2][0:4]
            if not year.isdigit(): return None
            year = int(year)
            if year == 0: return None
            choices = self.randomyears(year)
            return Q(question.format(name),
                [(year,None) for year in choices],
                year,
                keeporder=True)
        return None

    def q_birthplace(self, question = _("Where was {} born?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and birth.place.name and birth.date and death.date",
                expressions="self,birth.place,str(birth.date),str(death.date)",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            place = row[1]
            by = row[2][0:4]
            dy = row[3][0:4]
            if not place: return None
            if not by.isdigit(): return None
            if not dy.isdigit(): return None
            name = "{} ({}-{})".format(name,by,dy)
            choices = self.randomplaceobjects([place],self.numchoices-1)
            choices.append(place)
            return Q(question.format(name),
                [(p.longname,p) for p in choices],
                place.longname)
        return None

    def q_deathplace(self, question = _("Where did {} die?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and death.place.name and birth.date and death.date",
                expressions="self,death.place,str(birth.date),str(death.date)",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            place = row[1]
            by = row[2][0:4]
            dy = row[3][0:4]
            if not place: return None
            if not by.isdigit(): return None
            if not dy.isdigit(): return None
            name = "{} ({}-{})".format(name,by,dy)
            choices = self.randomplaceobjects([place],self.numchoices-1)
            choices.append(place)
            return Q(question.format(name),
                [(p.longname,p) for p in choices],
                place.longname)
        return None

    def q_born_in(self, question = _("Who was born in {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and birth.place.name and birth.date and death.date",
                expressions="self,birth.placename,str(birth.date),str(death.date)",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            selected_person = row[0]
            name = pname(row[0])
            place = row[1]
            by = row[2][0:4]
            dy = row[3][0:4]
            if not place: continue
            if not by.isdigit(): continue
            if not dy.isdigit(): continue
            name = "{} ({}-{})".format(name,by,dy)

            handles = self.randomhandles("People")
            try:
                result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                    filter="surname and birth.placename != '{}'".format(place),
                    expressions="self,birth.placename,str(birth.date),str(death.date)",
                    ).rows
            except:
                return None
            choices = []
            for row in result:
                choices.append(row[0])
            choices = choices[0:self.numchoices-1]
            choices.append(selected_person)
            if len(choices) != self.numchoices: return None
            return Q(question.format(place),
                [(pname(p),p) for p in choices],
                pname(selected_person))
        return None

    def q_died_in(self, question = _("Who died in {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and death.place.name and birth.date and death.date",
                expressions="self,death.placename,str(birth.date),str(death.date)",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            selected_person = row[0]
            name = pname(row[0])
            place = row[1]
            by = row[2][0:4]
            dy = row[3][0:4]
            if not place: return None
            if not by.isdigit(): return None
            if not dy.isdigit(): return None
            name = "{} ({}-{})".format(name,by,dy)

            handles = self.randomhandles("People")
            try:
                result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                    filter="surname and death.placename != '{}'".format(place),
                    expressions="self,death.placename,str(birth.date),str(death.date)",
                    ).rows
            except:
                return None
            choices = []
            for row in result:
                choices.append(row[0])
            choices = choices[0:self.numchoices-1]
            choices.append(selected_person)
            if len(choices) != self.numchoices: return None
            return Q(question.format(place),
                [(pname(p),p) for p in choices],
                pname(selected_person))
        return None

    def q_spouse(self, question = _("Who is the spouse of {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and spouses",
                expressions="self,spouses[0],spouses[0].gender",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            spouse = row[1]
            gender = row[2]
            choices = self.randompeopleobjects([spouse], self.numchoices-1, gender=gender)
            choices.append(spouse)
            return Q(question.format(name),
                [(pname(p),p) for p in choices],
                pname(spouse))
        return None


    def q_father(self, question = _("Who is the father of {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and father",
                expressions="self,father",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            father = row[1]
            choices = self.randompeopleobjects([father], self.numchoices-1, gender='M')
            choices.append(father)
            return Q(question.format(name),
                [(pname(p),p) for p in choices],
                pname(father))
        return None


    def q_mother(self, question = _("Who is the mother of {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and mother",
                expressions="self,mother",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            mother = row[1]
            choices = self.randompeopleobjects([mother], self.numchoices-1, gender='F')
            choices.append(mother)
            return Q(question.format(name),
                [(pname(p),p) for p in choices],
                pname(mother))
        return None

    def q_child(self, question = _("Who is a child of {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="len(children) > 0",
                expressions="self, children",
                ).rows
        except:
            return None
        for row in result:
            parentname = pname(row[0])
            children = row[1]
            child = random.choice(children)
            choices = self.randompeopleobjects(children, self.numchoices-1)
            choices.append(child)
            return Q(question.format(parentname),
                [(pname(p),p) for p in choices],
                pname(child))
        return None

    def q_child_family(self, question = _("Who is a child of {} and {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("Families")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "Families", handles=handles,
                filter="father.surname and mother and len(children) > 0",
                expressions="father,mother,children",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            father = pname(row[0])
            mother = pname(row[1])
            children = row[2]
            child = random.choice(children)
            choices = self.randompeopleobjects(children, self.numchoices-1)
            choices.append(child)
            return Q(question.format(father,mother),
                [(pname(p),p) for p in choices],
                pname(child))
        return None

    def q_grandfather(self, question = _("Who is the grandfather of {}?")):
        # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and father and (father.father or mother.father)",
                expressions="self, father.father, mother.father",
                ).rows
        except:
            return None
        #print("result:", result)
        for row in result:
            name = pname(row[0])
            fathers = [p for p in row[1:] if p]
            father = random.choice(fathers)
            excluded = fathers
            choices = self.randompeopleobjects(excluded, self.numchoices-1, gender='M')
            choices.append(father)
            return Q(question.format(name),
                [(pname(c),c) for c in choices],
                pname(father)
            )
        return None

    def q_grandmother(self, question = _("Who is the grandmother of {}?")):
        # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and father and (father.mother or mother.mother)",
                expressions="self, father.mother, mother.mother",
                ).rows
        except:
            return None
        for row in result:
            name = pname(row[0])
            mothers = [p for p in row[1:] if p]
            mother = random.choice(mothers)
            excluded = mothers
            choices = self.randompeopleobjects(excluded, self.numchoices-1, gender='F')
            choices.append(mother)
            return Q(question.format(name),
                [(pname(c),c) for c in choices],
                pname(mother)
            )
        return None

    def q_grandchild(self,question=_("Who is the grandchild of {}?")):
        # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                filter="surname and father and (father.mother or mother.mother)",
                expressions="self, father.father, father.mother, mother.father, mother.mother",
                ).rows
        except:
            return None
        for row in result:
            child = row[0]
            grandparents = [p for p in row[1:] if p]
            grandparent = random.choice(grandparents)
            excluded = [child]
            choices = self.randompeopleobjects(excluded, self.numchoices-1, gender='F')
            choices.append(child)
            return Q(question.format(grandparent.name),
                [(pname(c),c) for c in choices],
                pname(child)
            )
        return None


    def q_occupation(self, question = _("What was the occupation of {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                statements="occups = [e.description for e in events if e.type == 'Occupation']",
                filter="surname and occups",
                expressions="self,occups",
                ).rows
        except:
            return None
        for row in result:
            name = pname(row[0])
            occups = row[1]
            occup = random.choice(occups)
            choices = self.randomoccupations(occups, self.numchoices-1)
            choices.append(occup)
            return Q(question.format(name),
                [(occup,None) for occup in choices],
                occup)
        return None

    def q_whose_occupation(self, question = _("Whose occupation was {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                statements="occups = [e.description for e in events if e.type == 'Occupation']",
                filter="surname and occups",
                expressions="self,occups",
                ).rows
        except:
            return None
        #print("result:", result)
        #pprint(result)
        occupmap = defaultdict(list)
        allpeople = []
        for row in result:
            person = row[0]
            occups = row[1]
            for occup in occups:
                occupmap[occup].append(person)
            allpeople.append(person)
            if len(allpeople) == self.numchoices: break

        if len(allpeople) < self.numchoices:
            return None
        allpeople = allpeople[0:self.numchoices]
        for occup,persons in occupmap.items():
            if len(persons) == 1:
                selected_person = persons[0]
                gramps_ids = [p.gramps_id for p in allpeople]
                if selected_person.gramps_id not in gramps_ids:
                    allpeople.insert(0, selected_person)
                allpeople = allpeople[0:self.numchoices]
                return Q(question.format(occup),
                    [(p.name,p) for p in allpeople],
                    selected_person.name)
        return None


    def q_residence(self, question = _("Where did {} live?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People")
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                statements="residences = [e.place for e in events if e.type == 'Residence']",
                filter="surname and residences",
                expressions="self,residences",
                ).rows
        except:
            traceback.print_exc()
            return None
        #print("result:", result)
        for row in result:
            person = row[0]
            places = row[1]
            place = random.choice(places)
            choices = self.randomplaceobjects(excluded=places, numchoices=self.numchoices-1)
            choices.append(place)
            return Q(question.format(pname(person)),
                [(c.longname, c) for c in choices],
                place.longname,
            )
        return None

    def q_residence2(self, question = _("Who lived in {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("People",500)
        try:
            result = supertool_execute(dbstate=self.dbstate, category= "People", handles=handles,
                statements="residences = [e.placename for e in events if e.type == 'Residence' and e.placename]",
                filter="surname and residences",
                expressions="self, residences",
                ).rows
        except:
            traceback.print_exc()
            return None
        #print("result:", result)
        placemap = defaultdict(list)
        allpeople = []
        for row in result:
            person = row[0]
            places = row[1]
            for place in places:
                placemap[place].append(person)
            allpeople.append(person)
        for place, persons in placemap.items():
            if len(persons) == 1:
                selected_person = persons[0]
                choices = [selected_person]
                for p in allpeople:
                    if p.gramps_id != selected_person.gramps_id:
                        choices.append(p)
                        if len(choices) == self.numchoices:
                            break
                return Q(question.format(place),
                    [(pname(p),p) for p in choices],
                    pname(selected_person),
                )
        return None

    def xxxq_includes(self, question = _("Which place includes {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("Places")
        try:
            result = supertool_execute(dbstate=self.dbstate, category="Places", handles=handles,
                filter="len(enclosed_by) > 0",
                expressions="name, type, enclosed_by",
                ).rows
        except:
            traceback.print_exc()
            return None
        print("result:", result)
        for row in result:
            place = row[0]
            type = row[1]
            enclosed_by = row[2]
            choices1 = self.randomplaceobjects(excluded=enclosed_by, numchoices=50)#self.numchoices-1)
            selected = random.choice(enclosed_by)
            choices = []
            for p in choices1:
                if len(choices) == self.numchoices-1: break
                if p.type == selected.type:
                    choices.append(place)
            choices.append(selected)
            if len(choices) < self.numchoices: return None  # fails
            return Q(question.format(place),
                [(p.longname,p) for p in choices],
                selected.longname,
            )
        return None

    def q_includes(self, question = _("Which place includes {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("Places")
        try:
            result = supertool_execute(dbstate=self.dbstate, category="Places", handles=handles,
                filter="len(enclosed_by) > 0",
                expressions="name, type, enclosed_by",
                ).rows
        except:
            traceback.print_exc()
            return None
        print("result:", result)
        if len(result) == 0: return None
        row = random.choice(result)
        print("row:", row)
        placename = row[0]
        type = row[1]
        enclosed_by = row[2]
        selected = random.choice(enclosed_by)
        print("selected:", selected)

        try:
            result = supertool_execute(dbstate=self.dbstate, category="Places", handles=handles,
                filter="type == '{}'".format(selected.type),
                expressions="self"
                ).rows
        except:
            traceback.print_exc()
            return None

        random.shuffle(result)
            
        choices = []
        print("result2:")
        pprint(result)
        for row in result:
            p = row[0]
            if len(choices) == self.numchoices-1: break
            if p.gramps_id == selected.gramps_id: continue
            if p.gramps_id in [p2.gramps_id for p2 in enclosed_by]: continue
            choices.append(p)
        choices.append(selected)
        if len(choices) < self.numchoices: return None  # fails
        return Q(question.format(placename),
            [(p.longname,p) for p in choices],
            selected.longname,
        )
        return None

    def q_included(self, question = _("Which place is included in {}?")):
    # type: (str) -> Optional[Q]
        handles = self.randomhandles("Places")
        try:
            result = supertool_execute(dbstate=self.dbstate, category="Places", handles=handles,
                filter="len(encloses) > 0",
                expressions="longname, encloses",
                ).rows
        except:
            traceback.print_exc()
            return None
        #print("result:", result)
        for row in result:
            place = row[0]
            encloses = row[1]
            choices = self.randomplaceobjects(excluded=encloses, numchoices=self.numchoices-1)
            selected = random.choice(encloses)
            choices.append(selected)
            return Q(question.format(place),
                [(p.name, p) for p in choices],
                selected.name,
            )
        return None



#------------------------------------------------------------------------
#
# Options
#
#------------------------------------------------------------------------
class Options(tool.ToolOptions):
    pass



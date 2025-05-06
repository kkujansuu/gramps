#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2020-2025  Kari Kujansuu
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

from gramps.grampsapp import args
from gramps.gen.db.txn import DbTxn
from contextlib import contextmanager
from gramps.gui.editors.editperson import EditPerson

"""Tools/Database Processing/Find Possible Duplicate People"""

import csv
import itertools
import os
import random
import sqlite3
import time
import traceback

from pathlib import Path

# -------------------------------------------------------------------------
#
# GNOME libraries
#
# -------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Pango

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import URL_MANUAL_PAGE
from gramps.gen.const import URL_MANUAL_SECT3
from gramps.gen.datehandler import get_date
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.errors import MergeError
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib import Event, Person, Span
from gramps.gen.merge import MergePersonQuery
from gramps.gen.plug.report import utils
from gramps.gen.soundex import soundex, compare

from gramps.gui.dialog import ErrorDialog, WarningDialog
from gramps.gui.dialog import RunDatabaseRepair
from gramps.gui.dialog import OkDialog
from gramps.gui.display import display_help
from gramps.gui.glade import Glade
from gramps.gui.listmodel import ListModel
from gramps.gui.managedwindow import ManagedWindow

# from gramps.gui.merge import MergePerson
from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter

_ = glocale.translation.sgettext


# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
_val2label = {
    0.25: _("Low"),
    1.0: _("Medium"),
    2.0: _("High"),
}

WIKI_HELP_PAGE = "%s_-_Tools" % URL_MANUAL_PAGE
WIKI_HELP_SEC = _("manual|Find_Possible_Duplicate_People")

from gramps.gen.config import config as configman

config = configman.register_manager("finddupes4")
config.register("defaults.encoding", "utf-8")
config.register("defaults.delimiter", "comma")
config.register("defaults.font", "")
config.register("defaults.last_filename", "")


# -------------------------------------------------------------------------
#
#
#
# -------------------------------------------------------------------------
def is_initial(name):
    if len(name) > 2:
        return 0
    elif len(name) == 2:
        if name[0] == name[0].upper() and name[1] == ".":
            return 1
    else:
        return name[0] == name[0].upper()


class NumberEntry(Gtk.Entry):
    def __init__(self):
        Gtk.Entry.__init__(self)
        self.connect("changed", self.on_changed)

    def on_changed(self, *args):
        text = self.get_text().strip()
        self.set_text("".join([i for i in text if i in "0123456789"]))


class DummyTxn:
    "Implements nested transactions"

    def __init__(self, trans):
        if trans is None:
            raise RuntimeError("Need a transaction")
        self.trans = trans

        class _Txn:
            def __init__(self, msg, db):
                pass

            def __enter__(self):
                return trans

            def __exit__(self, *args):
                return False

        self.txn = _Txn


# -------------------------------------------------------------------------
#
# The Actual tool.
#
# -------------------------------------------------------------------------
class Tool(tool.Tool, ManagedWindow):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)
        self.dbstate = dbstate
        self.db = dbstate.db

        if not user.uistate:
            self.run_cli()
            return

        self.map = {}
        self.list = []
        self.index = 0
        self.removed = {}
        self.update = callback
        self.use_soundex = 1
        self.debug = False

        self.setup_db()
        dbstate.connect("database-changed", self.db_changed)

        top = Glade(
            toplevel="finddupes", also_load=["liststore1", "adjustment1", "adjustment2"]
        )

        # retrieve options
        threshold = self.options.handler.options_dict["threshold"]
        self.use_soundex = self.options.handler.options_dict["soundex"]
        all_first_names = self.options.handler.options_dict["all_first_names"]
        self.skip_no_surname = self.options.handler.options_dict["skip_no_surname"]
        self.skip_no_birth_date = self.options.handler.options_dict["skip_no_birth_date"]
        self.date_tolerance = self.options.handler.options_dict["date_tolerance"]
        self.random_percent = self.options.handler.options_dict["random_percent"]
        self.use_exclusions = self.options.handler.options_dict["use_exclusions"]

        my_menu = Gtk.ListStore(str, object)
        for val in sorted(_val2label):
            my_menu.append([_val2label[val], val])

        self.soundex_obj = top.get_object("soundex")
        self.soundex_obj.set_active(self.use_soundex)
        self.soundex_obj.show()

        self.all_first_names_obj = top.get_object("all_first_names")
        self.all_first_names_obj.set_active(all_first_names)
        self.all_first_names_obj.show()

        self.skip_no_surname_obj = top.get_object("skip_no_surname")
        self.skip_no_surname_obj.set_active(self.skip_no_surname)

        self.skip_no_birth_date_obj = top.get_object("skip_no_birth_date")
        self.skip_no_birth_date_obj.set_active(self.skip_no_birth_date)

        self.use_exclusions_obj = top.get_object("use_exclusions")
        self.use_exclusions_obj.set_active(self.use_exclusions)

        self.menu = top.get_object("menu")
        self.menu.set_model(my_menu)
        self.menu.set_active(0)

        self.date_tolerance_obj = top.get_object("date_tolerance")
        self.date_tolerance_obj.set_value(self.date_tolerance)

        self.random_percent_obj = top.get_object("random_percent")
        self.random_percent_obj.set_value(self.random_percent)

        window = top.toplevel
        self.set_window(
            window, top.get_object("title"), _("Find Possible Duplicate People")
        )
        self.setup_configs("interface.duplicatepeopletool", 350, 220)

        top.connect_signals(
            {
                "on_do_merge_clicked": self.__dummy,
                "on_help_show_clicked": self.__dummy,
                "on_delete_show_event": self.__dummy,
                "on_merge_ok_clicked": self.on_merge_ok_clicked,
                "destroy_passed_object": self.close,
                "on_help_clicked": self.on_help_clicked,
                "on_delete_merge_event": self.close,
                "on_delete_event": self.close,
                "on_load_csv_clicked": self.load_csv,
            }
        )

        self.matches_list = None
        self.show()

    def run_cli(self):
        # retrieve options
        self.threshold = self.options.handler.options_dict["threshold"]
        self.use_soundex = self.options.handler.options_dict["soundex"]
        self.all_first_names = self.options.handler.options_dict["all_first_names"]
        self.date_tolerance = self.options.handler.options_dict["date_tolerance"]
        self.random_percent = self.options.handler.options_dict["random_percent"]
        self.skip_no_surname = self.options.handler.options_dict["skip_no_surname"]
        self.skip_no_birth_date = self.options.handler.options_dict["skip_no_birth_date"]
        self.use_exclusions = self.options.handler.options_dict["use_exclusions"]
        self.progress = None

        self.find_potentials(self.threshold, self.random_percent)
        for p1key, (p2key, chance) in sorted(self.map.items(), key=lambda item: item[1][1] ,reverse=True):
            p1 = self.db.get_person_from_handle(p1key)
            p2 = self.db.get_person_from_handle(p2key)
            name1 = name_displayer.display(p1)
            name2 = name_displayer.display(p2)
            print(f"{chance:2.2f} {p1.gramps_id:10.10} {name1:30.30} -  {p2.gramps_id:10.10} {name2:30.30}")
            
    def db_changed(self, db):
        self.close()

    def build_menu_names(self, obj):
        return (_("Tool settings"), _("Find Duplicates tool"))

    def on_help_clicked(self, obj):
        """Display the relevant portion of Gramps manual"""

        display_help(WIKI_HELP_PAGE, WIKI_HELP_SEC)

    def setup_db(self):
        dbid = self.db.get_dbid()
        dbpath = configman.get("database.path")
        db_fname = Path(dbpath) / dbid / "exclusions.db"
        self.conn = sqlite3.connect(db_fname)
        cursor = self.conn.cursor()
        try:
            cursor.execute("create table if not exists exclusions (handle1 varchar, handle2 varchar, primary key(handle1, handle2))")
        except:
            traceback.print_exc()

        cursor.execute("select handle1, handle2 from exclusions")
        self.excluded = set((h1, h2) for (h1,h2) in cursor)
#        for h1, h2 in cursor:
#            self.excluded.add((h1,h2))

        cursor.close()
        self.conn.commit()
                

    def ancestors_of(self, p1_id, id_list):
        if (not p1_id) or (p1_id in id_list):
            return
        id_list.append(p1_id)
        p1 = self.db.get_person_from_handle(p1_id)
        f1_id = p1.get_main_parents_family_handle()
        if f1_id:
            f1 = self.db.get_family_from_handle(f1_id)
            self.ancestors_of(f1.get_father_handle(), id_list)
            self.ancestors_of(f1.get_mother_handle(), id_list)

    def on_merge_ok_clicked(self, obj):
        if self.matches_list and self.matches_list.opened:
            self.matches_list.close()
        threshold = self.menu.get_model()[self.menu.get_active()][1]
        self.use_soundex = int(self.soundex_obj.get_active())
        self.all_first_names = int(self.all_first_names_obj.get_active())
        self.skip_no_surname = int(self.skip_no_surname_obj.get_active())
        self.skip_no_birth_date = int(self.skip_no_birth_date_obj.get_active())
        self.use_exclusions = int(self.use_exclusions_obj.get_active())
        self.random_percent = int(self.random_percent_obj.get_value())
        try:
            self.date_tolerance = int(self.date_tolerance_obj.get_value())
        except:
            OkDialog(
                _("Invalid number"),
                _("Date tolerance must be a number"),
                parent=self.uistate.window,
            )
            return

        self.progress = ProgressMeter(
            _("Find Duplicates"),
            _("Looking for duplicate people"),
            can_cancel=True,
        )

        try:
            t1 = time.time()
            self.find_potentials(threshold, self.random_percent)
            t2 = time.time()
            # import cProfile
            # cProfile.runctx('self.find_potentials(threshold)', globals(), locals())
        except AttributeError as msg:
            # RunDatabaseRepair(str(msg), parent=self.window)
            return

        self.progress.close()

        self.options.handler.options_dict["threshold"] = threshold
        self.options.handler.options_dict["soundex"] = self.use_soundex
        self.options.handler.options_dict["date_tolerance"] = self.date_tolerance
        self.options.handler.options_dict["all_first_names"] = self.all_first_names
        self.options.handler.options_dict["skip_no_surname"] = self.skip_no_surname
        self.options.handler.options_dict["skip_no_birth_date"] = self.skip_no_birth_date
        self.options.handler.options_dict["use_exclusions"] = self.use_exclusions
        self.options.handler.options_dict["random_percent"] = self.random_percent
        # Save options
        self.options.handler.save_options()

        if len(self.map) == 0:
            OkDialog(
                _("No matches found"),
                _("No potential duplicate people were found"),
                parent=self.window,
            )
        else:
            try:
                self.matches_list = DuplicatePeopleToolMatches(
                    self.dbstate,
                    self.uistate,
                    self.track,
                    self.list,
                    self.map,
                    self.conn,
                    self.excluded,
                    self.update,
                    time_elapsed=t2 - t1,
                )
            except WindowActiveError:
                pass

    def load_csv(self, obj):
        # type: (Gtk.Widget) -> None
        choose_file_dialog = CsvOpenFileChooserDialog(self.uistate)
        fname = "matches.csv"

        config.load()
        self.last_filename = config.get("defaults.last_filename")

        choose_file_dialog.set_current_name(fname)
        if self.last_filename:
            choose_file_dialog.set_filename(self.last_filename)

        while True:
            response = choose_file_dialog.run()
            if response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
                choose_file_dialog.destroy()
                return
            elif response == Gtk.ResponseType.OK:
                self.last_filename = choose_file_dialog.get_filename()
                delimiter = ","
                if choose_file_dialog.cb_comma.get_active():
                    delimiter = ","
                if choose_file_dialog.cb_semicolon.get_active():
                    delimiter = ";"
                encoding = "utf-8"
                if choose_file_dialog.cb_utf8.get_active():
                    encoding = "utf-8"
                if choose_file_dialog.cb_iso8859_1.get_active():
                    encoding = "iso8859-1"

                config.set("defaults.encoding", encoding)
                config.set("defaults.delimiter", delimiter)
                config.set("defaults.last_filename", self.last_filename)
                config.save()

                reader = csv.reader(
                    open(self.last_filename, encoding=encoding), delimiter=delimiter
                )
                self.map = {}
                for row in reader:
                    if len(row) == 0:
                        continue
                    [chance, gramps_id1, gramps_id2, p1key, p2key, name1, name2] = row
                    if not self.db.has_person_handle(p1key):
                        continue
                    if not self.db.has_person_handle(p2key):
                        continue
                    self.map[p1key] = (p2key, float(chance))
                break

        choose_file_dialog.destroy()

        self.list = sorted(self.map)
        self.length = len(self.list)
        if self.matches_list and self.matches_list.opened:
            self.matches_list.close()
        try:
            self.matches_list = DuplicatePeopleToolMatches(
                self.dbstate, self.uistate, self.track, self.list, self.map, self.conn, self.excluded, self.update
            )
        except WindowActiveError:
            pass

    def find_potentials(self, thresh, random_percent):
        index = 0
        males = {}
        females = {}
        self.map = {}
        self.compared = {}

        length = self.db.get_number_of_people()

        if self.progress: self.progress.set_pass(_("Pass 1: Building preliminary lists"), length)

        pmap = {}  # build a cache of all Person objects
        for p1_id in self.db.iter_person_handles():
            if self.progress and self.progress.step():
                break  # canceled
            p1 = self.db.get_person_from_handle(p1_id)
            if p1.get_primary_name().get_regular_name() == "N N":
                continue

            if self.skip_no_birth_date:
                ref = p1.get_birth_ref()
                if not ref:
                    continue
                birth = self.dbstate.db.get_event_from_handle(ref.ref)
                if not birth.get_date_object().is_valid():
                    continue

            if self.skip_no_surname:
                surnames = get_surnames(p1.get_primary_name())
                if surnames == "N":
                    continue
                if surnames == "":
                    continue

            if self.skip_no_birth_date:
                ref = p1.get_birth_ref()
                if not ref:
                    continue
                birth = self.dbstate.db.get_event_from_handle(ref.ref)
                if not birth.get_date_object().is_valid():
                    continue

            for name in self.getnames(p1):
                surnames = get_surnames(name)
                key = self.gen_key(surnames)
                if p1.get_gender() == Person.MALE:
                    if key in males:
                        males[key].append(p1_id)
                    else:
                        males[key] = [p1_id]
                else:
                    if key in females:
                        females[key].append(p1_id)
                    else:
                        females[key] = [p1_id]
            pmap[p1_id] = p1

        if self.progress: self.progress.set_pass(_("Pass 2: Calculating potential matches"), length)

        for i, p1 in enumerate(pmap.values()):
            t1 = time.time()
            p1key = p1.handle
            if self.progress and self.progress.step():
                break  # canceled
            #p1 = self.db.get_person_from_handle(p1key)
            if random.random() >= random_percent / 100:
                continue

            surnames = get_surnames(p1.get_primary_name())
            key = self.gen_key(surnames)
            if p1.get_gender() == Person.MALE:
                remaining = males[key]
            else:
                remaining = females[key]

            # index = 0
            for p2key in remaining:
                # index += 1
                if p1key == p2key:
                    continue
                if self.use_exclusions:
                    if (p1key, p2key) in self.excluded:
                        continue
                    if (p2key, p1key) in self.excluded:
                        continue
                if p2key in self.map:
                    (v, c) = self.map[p2key]
                    if v == p1key:
                        continue

                # p2 = self.db.get_person_from_handle(p2key)
                p2 = pmap[p2key]

                chance = self.compare_people(p1, p2)
                if chance >= thresh:
                    if p1key in self.map:  # already found a match for p1
                        val = self.map[p1key]
                        if chance > val[1]:  # this is a better match
                            self.map[p1key] = (p2key, chance)
                    else:
                        self.map[p1key] = (p2key, chance)
            t2 = time.time()

        self.list = sorted(self.map)
        self.length = len(self.list)

    def gen_key(self, val):
        if self.use_soundex:
            try:
                return soundex(val)
            except UnicodeEncodeError:
                return val
        else:
            return val

    def getnames(self, p):
        return [p.get_primary_name()] + p.get_alternate_names()

    def compare_names(self, p1, p2):
        # compare all alternate names
        chance = max(
            self.name_match(name1, name2)
            for name1, name2 in itertools.product(self.getnames(p1), self.getnames(p2))
        )
        return chance

    def compare_people(self, p1, p2):
        if (p2.gramps_id, p1.gramps_id) in self.compared:
            return self.compared[(p2.gramps_id, p1.gramps_id)]
        self.p1 = p1
        self.p2 = p2

        chance = self.compare_names(p1, p2)
        if chance == -1:
            return -1

        birth1_ref = p1.get_birth_ref()
        if birth1_ref:
            birth1 = self.db.get_event_from_handle(birth1_ref.ref)
        else:
            birth1 = Event()

        death1_ref = p1.get_death_ref()
        if death1_ref:
            death1 = self.db.get_event_from_handle(death1_ref.ref)
        else:
            death1 = Event()

        birth2_ref = p2.get_birth_ref()
        if birth2_ref:
            birth2 = self.db.get_event_from_handle(birth2_ref.ref)
        else:
            birth2 = Event()

        death2_ref = p2.get_death_ref()
        if death2_ref:
            death2 = self.db.get_event_from_handle(death2_ref.ref)
        else:
            death2 = Event()

        value = self.date_match(birth1.get_date_object(), birth2.get_date_object())
        if value == -1:
            return -1
        chance += value
        #        value = self.date_match(death1.get_date_object(),
        #                                death2.get_date_object())
        #        if value == -1 :
        #            return -1
        #        chance += value

        value = self.place_match(birth1.get_place_handle(), birth2.get_place_handle())
        if value == -1:
            return -1
        chance += value

        value = self.place_match(death1.get_place_handle(), death2.get_place_handle())
        if value == -1:
            return -1
        chance += value

        ancestors = []
        self.ancestors_of(p1.get_handle(), ancestors)
        if p2.get_handle() in ancestors:
            return -1

        ancestors = []
        self.ancestors_of(p2.get_handle(), ancestors)
        if p1.get_handle() in ancestors:
            return -1

        f1_id = p1.get_main_parents_family_handle()
        f2_id = p2.get_main_parents_family_handle()

        if f1_id and f2_id:
            f1 = self.db.get_family_from_handle(f1_id)
            f2 = self.db.get_family_from_handle(f2_id)
            dad1_id = f1.get_father_handle()
            if dad1_id:
                dad1 = get_name_obj(self.db.get_person_from_handle(dad1_id))
            else:
                dad1 = None
            dad2_id = f2.get_father_handle()
            if dad2_id:
                dad2 = get_name_obj(self.db.get_person_from_handle(dad2_id))
            else:
                dad2 = None

            value = self.name_match(dad1, dad2)

            if value == -1:
                return -1

            chance += value

            mom1_id = f1.get_mother_handle()
            if mom1_id:
                mom1 = get_name_obj(self.db.get_person_from_handle(mom1_id))
            else:
                mom1 = None
            mom2_id = f2.get_mother_handle()
            if mom2_id:
                mom2 = get_name_obj(self.db.get_person_from_handle(mom2_id))
            else:
                mom2 = None

            value = self.name_match(mom1, mom2)
            if value == -1:
                return -1

            chance += value

        for f1_id in p1.get_family_handle_list():
            f1 = self.db.get_family_from_handle(f1_id)
            for f2_id in p2.get_family_handle_list():
                f2 = self.db.get_family_from_handle(f2_id)
                if p1.get_gender() == Person.FEMALE:
                    father1_id = f1.get_father_handle()
                    father2_id = f2.get_father_handle()
                    if father1_id and father2_id:
                        if father1_id == father2_id:
                            chance += 1
                        else:
                            father1 = self.db.get_person_from_handle(father1_id)
                            father2 = self.db.get_person_from_handle(father2_id)
                            fname1 = get_name_obj(father1)
                            fname2 = get_name_obj(father2)
                            value = self.name_match(fname1, fname2)
                            if value != -1:
                                chance += value
                else:
                    mother1_id = f1.get_mother_handle()
                    mother2_id = f2.get_mother_handle()
                    if mother1_id and mother2_id:
                        if mother1_id == mother2_id:
                            chance += 1
                        else:
                            mother1 = self.db.get_person_from_handle(mother1_id)
                            mother2 = self.db.get_person_from_handle(mother2_id)
                            mname1 = get_name_obj(mother1)
                            mname2 = get_name_obj(mother2)
                            value = self.name_match(mname1, mname2)
                            if value != -1:
                                chance += value

        self.compared[(p1.gramps_id, p2.gramps_id)] = chance
        return chance

    def name_compare(self, s1, s2):
        if self.use_soundex:
            try:
                return compare(s1, s2)
            except UnicodeEncodeError:
                return s1 == s2
        else:
            return s1 == s2

# -------------------------------------------------------------------------
    def compare(str1, str2):
        "1 if strings are close. 0 otherwise."
        sdx1 = soundex(str1)
        sdx2 = soundex(str2)
        if sdx1 == "Z000":      # non-ascii string  
            return str1 == str2
        else:
            return sdx1 == sdx2
    
    def date_match(self, date1, date2):
        if date1.is_empty() or date2.is_empty():
#            return -1
            return 0
        if date1.is_equal(date2):
            return 1

        if date1.is_compound() or date2.is_compound():
            return self.range_compare(date1, date2)

        if date1.get_year() == date2.get_year():
            if date1.get_month() == date2.get_month():
                return 0.75
            if not date1.get_month_valid() or not date2.get_month_valid():
                return 0.75
            else:
                return 0.25
        elif abs(date1.get_year() - date2.get_year()) <= self.date_tolerance:
            return 0.5
        else:
            return -1

    def range_compare(self, date1, date2):
        start_date_1 = date1.get_start_date()[0:3]
        start_date_2 = date2.get_start_date()[0:3]
        stop_date_1 = date1.get_stop_date()[0:3]
        stop_date_2 = date2.get_stop_date()[0:3]

        # fix the order of dd,mm,yyyy => yyyy,mm,dd
        start_date_1 = list(reversed(start_date_1))
        start_date_2 = list(reversed(start_date_2))
        stop_date_1 = list(reversed(stop_date_1))
        stop_date_2 = list(reversed(stop_date_2))

        # stop date is [0,0,0] if not compound; this makes the code below more simple
        if not date1.is_compound():
            stop_date_1 = start_date_1
        if not date2.is_compound():
            stop_date_2 = start_date_2

        if stop_date_1[1] == 0:
            stop_date_1[1] = 12
        if stop_date_1[2] == 0:
            stop_date_1[2] = 31
        if stop_date_2[1] == 0:
            stop_date_2[1] = 12
        if stop_date_2[2] == 0:
            stop_date_2[2] = 31

        min_start = min(start_date_1[0], start_date_2[0])
        max_stop = max(stop_date_1[0], stop_date_2[0])
        if max_stop - min_start <= self.date_tolerance:
            if date1.is_compound() and date2.is_compound():
                if (
                    stop_date_1 >= start_date_2 and stop_date_2 >= start_date_1
                ):  # overlapping ranges
                    return 0.25
            elif date1.is_compound():
                if (
                    start_date_1 <= start_date_2 <= stop_date_1
                ):  # date2 within date1 range
                    return 0.5
            elif date2.is_compound():
                if (
                    start_date_2 <= start_date_1 <= stop_date_2
                ):  # date1 within date2 range
                    return 0.5

            # no overlap
            return 0.2
        return -1

    def name_match(self, name, name1):

        if not name1 or not name:
            return 0

        srn1 = get_surnames(name)
        sfx1 = name.get_suffix()
        srn2 = get_surnames(name1)
        sfx2 = name1.get_suffix()

        if not self.name_compare(srn1, srn2):
            return -1
        if sfx1 != sfx2:
            if sfx1 != "" and sfx2 != "":
                return -1

        list1 = name.get_first_name().replace("-", " ").split()
        list2 = name1.get_first_name().replace("-", " ").split()
        if len(list1) == 0 or len(list2) == 0:
            if self.all_first_names:
                return -1
            else:
                return 0.1
        if name.get_first_name() == name1.get_first_name():
            return 1
        else:
            if self.all_first_names:
                if len(list1) != len(list2):
                    return -1
                for n1 in list1:
                    if all(not self.name_compare(n1, n2) for n2 in list2):
                        return -1
                for n2 in list2:
                    if all(not self.name_compare(n1, n2) for n1 in list1):
                        return -1
                return 1
            if len(list1) < len(list2):
                return self.list_reduce(list1, list2)
            else:
                return self.list_reduce(list2, list1)

    def place_match(self, p1_id, p2_id):
        if p1_id == p2_id:
            return 1

        if not p1_id:
            name1 = ""
        else:
            p1 = self.db.get_place_from_handle(p1_id)
            name1 = p1.get_title()

        if not p2_id:
            name2 = ""
        else:
            p2 = self.db.get_place_from_handle(p2_id)
            name2 = p2.get_title()

        if not (name1 and name2):
            return 0
        if name1 == name2:
            return 1

        list1 = name1.replace(",", " ").split()
        list2 = name2.replace(",", " ").split()

        value = 0
        for name in list1:
            for name2 in list2:
                if name == name2:
                    value += 0.5
                elif name[0] == name2[0] and self.name_compare(name, name2):
                    value += 0.25
        return min(value, 1) if value else -1

    def list_reduce(self, list1, list2):
        value = 0
        for name in list1:
            for name2 in list2:
                if is_initial(name) and name[0] == name2[0]:
                    value += 0.25
                elif is_initial(name2) and name2[0] == name[0]:
                    value += 0.25
                elif name == name2:
                    value += 0.5
                elif name[0] == name2[0] and self.name_compare(name, name2):
                    value += 0.25
        return min(value, 1) if value else -1

    def __dummy(self, obj):
        """dummy callback, needed because a shared glade file is used for
        both toplevel windows and all signals must be handled.
        """
        pass


def get_year(dbstate, ref):
    y = ""
    if ref:
        event = dbstate.db.get_event_from_handle(ref.ref)
        date_object = event.get_date_object()
        if date_object:
            y = date_object.get_year()
            y2 = date_object.get_stop_year()
            if not y:
                y = ""
            elif y2 > y:
                y = "{y}-{y2}".format(y=y, y2=y2)
            else:
                y = "{y}".format(y=y)
    return str(y)


def get_years(dbstate, person):
    birthref = person.get_birth_ref()
    by = get_year(dbstate, birthref)
    deathref = person.get_death_ref()
    dy = get_year(dbstate, deathref)
    if by and dy:
        years = "b.{by} d.{dy}".format(by=by, dy=dy)
    elif by:
        years = "b.{by}".format(by=by)
    elif dy:
        years = "d.{dy}".format(dy=dy)
    else:
        years = ""
    return years


class DuplicatePeopleToolMatches(ManagedWindow):

    def __init__(
        self, dbstate, uistate, track, the_list, the_map, dbconnection, excluded, callback, time_elapsed=None
    ):
        ManagedWindow.__init__(self, uistate, track, self.__class__)

        self.dellist = set()
        self.dellist2 = set()  # list of pairs that are deleted from the list
        self.dellist3 = set()  # handles that were deleted because of a merge
        self.map = the_map
        self.length = len(the_list)
        self.update = callback
        self.db = dbstate.db
        self.dbstate = dbstate
        self.uistate = uistate
        self.time_elapsed = time_elapsed
        self.conn = dbconnection
        self.excluded = excluded

        top = Glade(toplevel="mergelist")
        window = top.toplevel
        self.set_window(window, top.get_object("title"), _("Potential Merges"))
        self.setup_configs("interface.duplicatepeopletoolmatches", 500, 350)

        self.mlist = top.get_object("mlist")
        self.mlist.set_hover_selection(True)

        top.connect_signals(
            {
                "destroy_passed_object": self.close,
                "on_do_compare_clicked": self.on_do_compare_clicked,
                "on_do_merge_clicked": self.on_do_merge_clicked,
                "on_help_show_clicked": self.on_help_clicked,
                "on_delete_show_event": self.close,
                "on_merge_ok_clicked": self.__dummy,
                "on_help_clicked": self.__dummy,
                "on_delete_merge_event": self.__dummy,
                "on_delete_event": self.__dummy,
                "on_save_csv_event": self.save_csv,
                "on_delete": self.delete_from_list,
            }
        )
        self.db.connect("person-delete", self.person_delete)

        mtitles = [
            (_("Rating"), 3, 75),
            (_("First Person"), 1, 400),
            (_("Second Person"), 2, 400),
            ("", -1, 0),
            ("", -1, 0),  # gramps id 1
            ("", -1, 0),  # gramps id 2
        ]
        self.list = ListModel(
            self.mlist,
            mtitles,
            mode=Gtk.SelectionMode.MULTIPLE,
            # mode=Gtk.SelectionMode.SINGLE,
            event_func=self.on_do_compare_clicked,
            right_click=self.on_right_click,
        )

        stats_text = _("Number of matches: {}").format(len(the_map))
        if time_elapsed is not None:
            stats_text += _("; elapsed time: {:1.2f}s").format(time_elapsed)
        label_stats = top.get_child_object("label_stats")
        label_stats.set_text(stats_text)
        self.redraw()
        self.show()

    def edit_person(self, menuitem, treeview, handle, name):
        self.uistate.set_active(handle, "Person")

    def on_right_click(self, treeview, event):
        (model, rows) = self.list.selection.get_selected_rows()
        if len(rows) != 1:
            return
        ref = Gtk.TreeRowReference(model, rows[0])
        iter_ = model.get_iter(ref.get_path())
        name1 = model.get_value(iter_, 1)
        name2 = model.get_value(iter_, 2)
        (self.p1, self.p2) = self.list.get_object(iter_)

        # copied from gramps/plugins/gramplet/coordinates.py:
        """
        Show a menu to select either Edit the selected event or
        the Place related to this event.
        """
        self.menu = Gtk.Menu()
        menu = self.menu
        menu.set_title(_("Edit"))
        title = _("Activate left person: ") + name1
        add_item = Gtk.MenuItem(label=title)
        add_item.connect("activate", self.edit_person, treeview, self.p1, name1)
        add_item.show()
        menu.append(add_item)
        title = _("Activate right person: ") + name2
        add_item = Gtk.MenuItem(label=title)
        add_item.connect("activate", self.edit_person, treeview, self.p2, name2)
        add_item.show()
        menu.append(add_item)
        menu.show()
        menu.popup(None, None, None, None, event.button, event.time)

    def build_menu_names(self, obj):
        return (_("Merge candidates"), _("Merge persons"))

    def on_help_clicked(self, obj):
        """Display the relevant portion of Gramps manual"""

        display_help(WIKI_HELP_PAGE, WIKI_HELP_SEC)

    def redraw(self):
        list = []
        for p1key, p1data in self.map.items():
            if p1key in self.dellist:
                continue
            (p2key, c) = p1data
            if p2key in self.dellist:
                continue
            if (p1key, p2key) in self.dellist2:
                continue
            if p1key == p2key:
                continue
            list.append((c, p1key, p2key))

        self.list.clear()
        self.download_list = []
        for c, p1key, p2key in sorted(list, reverse=True):
            c1 = "%5.2f" % c
            c2 = "%5.2f" % (100 - c)
            p1 = self.db.get_person_from_handle(p1key)
            p2 = self.db.get_person_from_handle(p2key)
            if not p1 or not p2:
                continue
            pn1 = name_displayer.display(p1)
            pn2 = name_displayer.display(p2)
            years1 = get_years(self.dbstate, p1)
            years2 = get_years(self.dbstate, p2)
            name1 = pn1 + " " + years1
            name2 = pn2 + " " + years2
            self.list.add(
                [c1, name1, name2, c2, p1.gramps_id, p2.gramps_id], (p1key, p2key)
            )
            self.download_list.append(
                [c1, p1.gramps_id, p2.gramps_id, p1key, p2key, name1, name2]
            )

    def on_do_compare_clicked(self, obj):

        (model, rows) = self.list.selection.get_selected_rows()
        if len(rows) != 1:
            return
        ref = Gtk.TreeRowReference(model, rows[0])
        iter = model.get_iter(ref.get_path())

        (self.p1, self.p2) = self.list.get_object(iter)
        MergePerson(
            self.dbstate,
            self.uistate,
            self.track,
            self.p1,
            self.p2,
            self.on_update,
            True,
        )

    def remove_estimated_birth(self, person, trans):
        deceased_tag = self.db.get_tag_from_name("deceased")
        if deceased_tag is None:
            return
        taglist = person.get_tag_list()
        if deceased_tag.handle in taglist:
            birth_event_ref = person.get_birth_ref()
            person._remove_handle_references("Event", [birth_event_ref.ref])
            self.db.commit_person(person, trans)

    def on_do_merge_clicked(self, obj):
        import gramps.gen.merge.mergepersonquery as mergemodule

        with self.nested_txn("Merging people", self.dbstate.db, mergemodule) as trans:
            handlepairlist = self.list.get_selected_objects()
            mergesets = self.genmerges(handlepairlist)  # set of ((i1,handle1),...)
            for mergeset in mergesets:
                phoenix_handle = mergeset[0][1]
                for _, titanic_handle in mergeset[1:]:
                    p1 = self.db.get_person_from_handle(phoenix_handle)
                    p2 = self.db.get_person_from_handle(titanic_handle)
                    self.remove_estimated_birth(p1, trans)
                    self.remove_estimated_birth(p2, trans)
                    query = mergemodule.MergePersonQuery(self.dbstate.db, p1, p2)
                    self.dellist.add(titanic_handle)
                    self.dellist3.add(titanic_handle)
                    query.execute()
        self.redraw()

    @contextmanager
    def nested_txn(self, title, db, mergemodule):
        with DbTxn(title, db) as trans:
            saved_dbtxn = mergemodule.DbTxn
            mergemodule.DbTxn = DummyTxn(trans).txn
            try:
                yield trans
            finally:
                mergemodule.DbTxn = saved_dbtxn

    def genmerges(self, mergepairs):
        """
        Generates the correct order of merges.
        Input: a list of handle pairs to be merged.
        Returns: set of tuples of tuples (i,handle)
            where i is the index of the handle in the original list
            The index is there so that the handles are in the same order as in the original list.
            I.e. the first handle in each tuple is the primary one.
        Because the same handle can occur multiple times in the list
        the merges cannot be done in the same order as the pairs appear.
        Example:
        Input: [(a,b),(c,d),(e,a),(c,f)]
        Output: {((0,a),(0,b),(2,e)),
                ((1,c),(1,d),(3,f))}
        """
        map = {}  # item -> itemlist

        for i, (a, b) in enumerate(mergepairs):
            if a in map:
                if b in map:
                    if map[a] == map[b]:
                        pass  # already in same set
                    else:  # merge two sets
                        map[a] = map[a] + map[b]
                else:  # b not in any set
                    map[a].append((i, b))
            else:  # a not in any set
                if b in map:
                    map[b].append((i, a))
                    map[a] = map[b]
                else:
                    map[a] = [(i, a), (i, b)]
            for i, x in map[a]:
                map[x] = map[a]

        return set([tuple(sorted(x)) for x in map.values()])

    def on_update(self):
        if self.db.has_person_handle(self.p1):
            titanic = self.p2
        else:
            titanic = self.p1
        self.dellist.add(titanic)
        self.update()
        self.redraw()
        self.uistate.set_active(self.p1, "Person")

    def update_and_destroy(self, obj):
        self.update(1)
        self.close()

    def person_delete(self, handle_list):
        """deal with person deletes outside of the tool"""
        if all(h in self.dellist3 for h in handle_list):
            return
        self.dellist.update(handle_list)
        self.redraw()

    def __dummy(self, obj):
        """dummy callback, needed because a shared glade file is used for
        both toplevel windows and all signals must be handled.
        """
        pass

    def xxxdelete_from_list(self, obj):
        store, iter = self.list.selection.get_selected()
        if not iter:
            return

        (p1, p2) = self.list.get_object(iter)
        self.dellist2.add((p1, p2))
        store.remove(iter)

    def delete_from_list(self, obj):
        (model, rows) = self.list.selection.get_selected_rows()
        cursor = self.conn.cursor()
        for row in rows[::-1]:
            ref = Gtk.TreeRowReference(model, row)
            iter = model.get_iter(ref.get_path())
            (p1, p2) = self.list.get_object(iter)
            cursor.execute("insert into exclusions (handle1, handle2) values (?,?) on conflict do nothing", [p1, p2])
            self.excluded.add((p1, p2))
            model.remove(iter)
        cursor.close()
        self.conn.commit()

    def save_csv(self, obj):
        # type: (Gtk.Widget) -> None
        choose_file_dialog = CsvFileChooserDialog(self.uistate)
        fname = "matches.csv"

        config.load()
        self.last_filename = config.get("defaults.last_filename")

        choose_file_dialog.set_current_name(fname)
        if self.last_filename:
            choose_file_dialog.set_filename(self.last_filename)

        while True:
            response = choose_file_dialog.run()
            if response == Gtk.ResponseType.CANCEL:
                break
            elif response == Gtk.ResponseType.DELETE_EVENT:
                break
            elif response == Gtk.ResponseType.OK:
                self.last_filename = choose_file_dialog.get_filename()
                delimiter = ","
                if choose_file_dialog.cb_comma.get_active():
                    delimiter = ","
                if choose_file_dialog.cb_semicolon.get_active():
                    delimiter = ";"
                encoding = "utf-8"
                if choose_file_dialog.cb_utf8.get_active():
                    encoding = "utf-8"
                if choose_file_dialog.cb_iso8859_1.get_active():
                    encoding = "iso8859-1"

                config.set("defaults.encoding", encoding)
                config.set("defaults.delimiter", delimiter)
                config.set("defaults.last_filename", self.last_filename)
                config.save()

                writer = csv.writer(
                    open(self.last_filename, "w", encoding=encoding, newline=""),
                    delimiter=delimiter,
                )

                #                 for row in self.download_list:
                #                     [c1, gramps_id1, gramps_id2, p1key, p2key, name1, name2] = row
                #                     if (p1key,p2key) in self.dellist2: continue
                #                     writer.writerow(row)

                for row in self.list.model:
                    [c, name1, name2, pct, grampsid1, grampsid2, (handle1, handle2)] = (
                        list(row)
                    )
                    csvrow = [
                        float(c.strip()),
                        grampsid1,
                        grampsid2,
                        handle1,
                        handle2,
                        name1,
                        name2,
                    ]
                    writer.writerow(csvrow)
                break

        choose_file_dialog.destroy()


class CsvFileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, uistate):
        Gtk.FileChooserDialog.__init__(
            self,
            title=_("Download results as a CSV file"),
            transient_for=uistate.window,
            action=Gtk.FileChooserAction.SAVE,
        )

        self.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("Save"), Gtk.ResponseType.OK
        )

        box = Gtk.VBox()
        box1 = Gtk.HBox()
        box2 = Gtk.HBox()

        config.load()
        encoding = config.get("defaults.encoding")
        delimiter = config.get("defaults.delimiter")

        self.cb_utf8 = Gtk.RadioButton.new_with_label_from_widget(None, "UTF-8")
        self.cb_iso8859_1 = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_utf8, "ISO8859-1"
        )
        if encoding == "iso8859-1":
            self.cb_iso8859_1.set_active(True)

        box1.add(Gtk.Label(_("Encoding:")))
        box1.add(self.cb_utf8)
        box1.add(self.cb_iso8859_1)
        frame1 = Gtk.Frame()
        frame1.add(box1)

        self.cb_comma = Gtk.RadioButton.new_with_label_from_widget(None, "comma")
        self.cb_semicolon = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_comma, "semicolon"
        )
        if delimiter == ";":
            self.cb_semicolon.set_active(True)

        box2.add(Gtk.Label(_("Delimiter:")))
        box2.add(self.cb_comma)
        box2.add(self.cb_semicolon)
        frame2 = Gtk.Frame()
        frame2.add(box2)
        box.set_spacing(5)
        box.add(frame1)
        box.add(frame2)
        box.show_all()
        self.set_extra_widget(box)
        self.set_do_overwrite_confirmation(True)

        filter_csv = Gtk.FileFilter()
        filter_csv.set_name(_("CSV files"))
        filter_csv.add_pattern("*.csv")
        self.add_filter(filter_csv)


class CsvOpenFileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, uistate):
        Gtk.FileChooserDialog.__init__(
            self,
            title=_("Load results from a CSV file"),
            transient_for=uistate.window,
            action=Gtk.FileChooserAction.OPEN,
        )

        self.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL, _("Open"), Gtk.ResponseType.OK
        )

        box = Gtk.VBox()
        box1 = Gtk.HBox()
        box2 = Gtk.HBox()

        config.load()
        encoding = config.get("defaults.encoding")
        delimiter = config.get("defaults.delimiter")

        self.cb_utf8 = Gtk.RadioButton.new_with_label_from_widget(None, "UTF-8")
        self.cb_iso8859_1 = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_utf8, "ISO8859-1"
        )
        if encoding == "iso8859-1":
            self.cb_iso8859_1.set_active(True)

        box1.add(Gtk.Label(_("Encoding:")))
        box1.add(self.cb_utf8)
        box1.add(self.cb_iso8859_1)
        frame1 = Gtk.Frame()
        frame1.add(box1)

        self.cb_comma = Gtk.RadioButton.new_with_label_from_widget(None, "comma")
        self.cb_semicolon = Gtk.RadioButton.new_with_label_from_widget(
            self.cb_comma, "semicolon"
        )
        if delimiter == ";":
            self.cb_semicolon.set_active(True)

        box2.add(Gtk.Label(_("Delimiter:")))
        box2.add(self.cb_comma)
        box2.add(self.cb_semicolon)
        frame2 = Gtk.Frame()
        frame2.add(box2)
        box.set_spacing(5)
        box.add(frame1)
        box.add(frame2)
        box.show_all()
        self.set_extra_widget(box)
        self.set_do_overwrite_confirmation(True)

        filter_csv = Gtk.FileFilter()
        filter_csv.set_name(_("CSV files"))
        filter_csv.add_pattern("*.csv")
        self.add_filter(filter_csv)


# -------------------------------------------------------------------------
#
#
#
# -------------------------------------------------------------------------
# def name_of(p):
#     if not p:
#         return ""
#     return "%s (%s)" % (name_displayer.display(p),p.get_handle())


def get_name_obj(person):
    if person:
        return person.get_primary_name()
    else:
        return None


def get_surnames(name):
    """Construct a full surname of the surnames"""
    return " ".join([surn.get_surname() for surn in name.get_surname_list()])


# copied from gramps/gui/merge/mergeperson.py:

# -------------------------------------------------------------------------
#
# Gramps constants
#
# -------------------------------------------------------------------------
WIKI_HELP_PAGE = URL_MANUAL_SECT3
WIKI_HELP_SEC = _("manual|Merge_People")
_GLADE_FILE = "mergeperson.glade"

# translators: needed for French, ignore otherwise
KEYVAL = _("%(key)s:\t%(value)s")

sex = (_("female"), _("male"), _("unknown"))


def name_of(person):
    """Return string with name and ID of a person."""
    if not person:
        return ""
    return "%s [%s]" % (name_displayer.display(person), person.get_gramps_id())


# -------------------------------------------------------------------------
#
# MergePerson
#
# -------------------------------------------------------------------------
class MergePerson(ManagedWindow):
    """
    Displays a dialog box that allows the persons to be combined into one.
    """

    def __init__(
        self,
        dbstate,
        uistate,
        track,
        handle1,
        handle2,
        cb_update=None,
        expand_context_info=True,
    ):
        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.database = dbstate.db
        self.pr1 = self.database.get_person_from_handle(handle1)
        self.pr2 = self.database.get_person_from_handle(handle2)
        self.update = cb_update

        import os

        glade_file = os.path.join(os.path.split(__file__)[0], _GLADE_FILE)
        self.define_glade("mergeperson", glade_file)
        self.set_window(
            self._gladeobj.toplevel, self.get_widget("person_title"), _("Merge People")
        )
        self.setup_configs("interface.merge-person", 700, 400)

        # Detailed selection widgets
        name1 = name_displayer.display_name(self.pr1.get_primary_name())
        name2 = name_displayer.display_name(self.pr2.get_primary_name())
        entry1 = self.get_widget("name1")
        entry2 = self.get_widget("name2")
        entry1.set_text(name1)
        entry2.set_text(name2)
        if entry1.get_text() == entry2.get_text():
            for widget_name in ("name1", "name2", "name_btn1", "name_btn2"):
                self.get_widget(widget_name).set_sensitive(False)

        entry1 = self.get_widget("gender1")
        entry2 = self.get_widget("gender2")
        entry1.set_text(sex[self.pr1.get_gender()])
        entry2.set_text(sex[self.pr2.get_gender()])
        if entry1.get_text() == entry2.get_text():
            for widget_name in ("gender1", "gender2", "gender_btn1", "gender_btn2"):
                self.get_widget(widget_name).set_sensitive(False)

        gramps1 = self.pr1.get_gramps_id()
        gramps2 = self.pr2.get_gramps_id()
        entry1 = self.get_widget("gramps1")
        entry2 = self.get_widget("gramps2")
        entry1.set_text(gramps1)
        entry2.set_text(gramps2)
        if entry1.get_text() == entry2.get_text():
            for widget_name in ("gramps1", "gramps2", "gramps_btn1", "gramps_btn2"):
                self.get_widget(widget_name).set_sensitive(False)

        # Main window widgets that determine which handle survives
        rbutton1 = self.get_widget("handle_btn1")
        rbutton_label1 = self.get_widget("label_handle_btn1")
        rbutton_label2 = self.get_widget("label_handle_btn2")
        rbutton_label1.set_label(name1 + " [" + gramps1 + "]")
        rbutton_label2.set_label(name2 + " [" + gramps2 + "]")
        rbutton1.connect("toggled", self.on_handle1_toggled)
        expander2 = self.get_widget("expander2")
        self.expander_handler = expander2.connect(
            "notify::expanded", self.cb_expander2_activated
        )
        expander2.set_expanded(expand_context_info)

        self.connect_button("person_help", self.cb_help)
        self.connect_button("person_ok", self.cb_merge)
        self.connect_button("person_cancel", self.close)

        activate_1 = self.get_widget("activate_1")
        activate_2 = self.get_widget("activate_2")
        activate_1.connect("button-press-event", self.activate_person, handle1)
        activate_2.connect("button-press-event", self.activate_person, handle2)

        self.show()

    def on_handle1_toggled(self, obj):
        """Preferred person changes"""
        if obj.get_active():
            self.get_widget("name_btn1").set_active(True)
            self.get_widget("gender_btn1").set_active(True)
            self.get_widget("gramps_btn1").set_active(True)
        else:
            self.get_widget("name_btn2").set_active(True)
            self.get_widget("gender_btn2").set_active(True)
            self.get_widget("gramps_btn2").set_active(True)

    def activate_person(self, _widget, event, handle):
        self.uistate.set_active(handle, "Person")

    def cb_expander2_activated(self, obj, param_spec):
        """Context Information expander is activated"""
        if obj.get_expanded():
            text1 = self.get_widget("text1")
            text2 = self.get_widget("text2")
            self.display(text1.get_buffer(), self.pr1)
            self.display(text2.get_buffer(), self.pr2)
            obj.disconnect(self.expander_handler)

    def add(self, tobj, tag, text):
        """Add text text to text buffer tobj with formatting tag."""
        text += "\n"
        tobj.insert_with_tags(tobj.get_end_iter(), text, tag)

    def display(self, tobj, person):
        """Fill text buffer tobj with detailed info on person person."""
        normal = tobj.create_tag()
        normal.set_property("indent", 10)
        normal.set_property("pixels-above-lines", 1)
        normal.set_property("pixels-below-lines", 1)
        indent = tobj.create_tag()
        indent.set_property("indent", 30)
        indent.set_property("pixels-above-lines", 1)
        indent.set_property("pixels-below-lines", 1)
        title = tobj.create_tag()
        title.set_property("weight", Pango.Weight.BOLD)
        title.set_property("scale", 1.2)

        self.normal = normal
        self.indent = indent
        self.title = title

        self.tag_underline = tobj.create_tag(
            "underline", underline=Pango.Underline.SINGLE
        )
        self.tag_underline.set_property("foreground", "blue")

        # self.add(tobj, self.tag_underline, "activate")
        self.add(tobj, title, name_displayer.display(person))
        self.add(
            tobj, normal, KEYVAL % {"key": _("ID"), "value": person.get_gramps_id()}
        )
        self.add(
            tobj,
            normal,
            KEYVAL % {"key": _("Gender"), "value": sex[person.get_gender()]},
        )
        bref = person.get_birth_ref()
        if bref:
            self.add(
                tobj,
                normal,
                KEYVAL % {"key": _("Birth"), "value": self.get_event_info(bref.ref)},
            )
        dref = person.get_death_ref()
        if dref:
            self.add(
                tobj,
                normal,
                KEYVAL % {"key": _("Death"), "value": self.get_event_info(dref.ref)},
            )

        nlist = person.get_alternate_names()
        if len(nlist) > 0:
            self.add(tobj, title, _("Alternate Names"))
            for name in nlist:
                self.add(tobj, normal, name_displayer.display_name(name))

        elist = person.get_event_ref_list()
        if len(elist) > 0:
            self.add(tobj, title, _("Events"))
            for event_ref in person.get_event_ref_list():
                event_handle = event_ref.ref
                role = event_ref.get_role()
                name = str(self.database.get_event_from_handle(event_handle).get_type())
                ev_info = self.get_event_info(event_handle)
                if role.is_primary():
                    self.add(tobj, normal, KEYVAL % {"key": name, "value": ev_info})
                else:
                    self.add(
                        tobj,
                        normal,  # translators: needed for French
                        "%(name)s (%(role)s):\t%(info)s"
                        % {"name": name, "role": role, "info": ev_info},
                    )
        plist = person.get_parent_family_handle_list()

        if len(plist) > 0:
            self.add(tobj, title, _("Parents"))
            for fid in person.get_parent_family_handle_list():
                (fname, mname, gid) = self.get_parent_info(fid)
                self.add(tobj, normal, KEYVAL % {"key": _("Family ID"), "value": gid})
                if fname:
                    self.add(
                        tobj, indent, KEYVAL % {"key": _("Father"), "value": fname}
                    )
                if mname:
                    self.add(
                        tobj, indent, KEYVAL % {"key": _("Mother"), "value": mname}
                    )

                self.add_family_events(tobj, fid)
        else:
            self.add(tobj, normal, _("No parents found"))

        self.add(tobj, title, _("Spouses"))
        slist = person.get_family_handle_list()
        if len(slist) > 0:
            for fid in slist:
                (fname, mname, pid) = self.get_parent_info(fid)
                family = self.database.get_family_from_handle(fid)
                self.add(tobj, normal, KEYVAL % {"key": _("Family ID"), "value": pid})
                spouse_id = utils.find_spouse(person, family)
                if spouse_id:
                    spouse = self.database.get_person_from_handle(spouse_id)
                    self.add(
                        tobj,
                        indent,
                        KEYVAL % {"key": _("Spouse"), "value": name_of(spouse)},
                    )
                relstr = str(family.get_relationship())
                self.add(tobj, indent, KEYVAL % {"key": _("Type"), "value": relstr})
                event = utils.find_marriage(self.database, family)
                if event:
                    m_info = self.get_event_info(event.get_handle())
                    self.add(
                        tobj, indent, KEYVAL % {"key": _("Marriage"), "value": m_info}
                    )
                for child_ref in family.get_child_ref_list():
                    child = self.database.get_person_from_handle(child_ref.ref)
                    bref = child.get_birth_ref()
                    # name = name_of(child)
                    name = name_displayer.display(child)
                    if bref:
                        birth_info = self.get_event_info(bref.ref)
                        name += " b." + birth_info
                    self.add(tobj, indent, KEYVAL % {"key": _("Child"), "value": name})
                # self.add_family_events(tobj, fid)
        else:
            self.add(tobj, normal, _("No spouses or children found"))

        alist = person.get_address_list()
        if len(alist) > 0:
            self.add(tobj, title, _("Addresses"))
            for addr in alist:
                # TODO for Arabic, should the next line's comma be translated?
                location = ", ".join(
                    [
                        addr.get_street(),
                        addr.get_city(),
                        addr.get_state(),
                        addr.get_country(),
                        addr.get_postal_code(),
                        addr.get_phone(),
                    ]
                )
                self.add(tobj, normal, location.strip())

    def add_family_events(self, tobj, fid):
        family = self.database.get_family_from_handle(fid)

        elist = family.get_event_ref_list()
        if len(elist) > 0:
            for event_ref in elist:
                event_handle = event_ref.ref
                role = event_ref.get_role()
                name = str(self.database.get_event_from_handle(event_handle).get_type())
                ev_info = self.get_event_info(event_handle)
                if role.is_primary():
                    self.add(
                        tobj, self.normal, KEYVAL % {"key": name, "value": ev_info}
                    )
                else:
                    self.add(
                        tobj,
                        self.normal,  # translators: needed for French
                        "%(name)s (%(role)s):\t%(info)s"
                        % {"name": name, "role": role, "info": ev_info},
                    )

    def get_parent_info(self, fid):
        """Return tuple of father name, mother name and family ID"""
        family = self.database.get_family_from_handle(fid)
        father_id = family.get_father_handle()
        mother_id = family.get_mother_handle()
        if father_id:
            father = self.database.get_person_from_handle(father_id)
            fname = name_of(father)
        else:
            fname = ""
        if mother_id:
            mother = self.database.get_person_from_handle(mother_id)
            mname = name_of(mother)
        else:
            mname = ""
        return (fname, mname, family.get_gramps_id())

    def get_event_info(self, handle):
        """Return date and place of an event as string."""
        date = ""
        place = ""
        if handle:
            event = self.database.get_event_from_handle(handle)
            date = get_date(event)
            place = place_displayer.display_event(self.database, event)
            if date:
                return ("%s, %s" % (date, place)) if place else date
            else:
                return place or ""
        else:
            return ""

    def cb_help(self, obj):
        """Display the relevant portion of Gramps manual"""
        display_help(webpage=WIKI_HELP_PAGE, section=WIKI_HELP_SEC)

    def cb_merge(self, obj):
        """
        Perform the merge of the persons when the merge button is clicked.
        """
        self.uistate.set_busy_cursor(True)
        use_handle1 = self.get_widget("handle_btn1").get_active()
        if use_handle1:
            phoenix = self.pr1
            titanic = self.pr2
        else:
            phoenix = self.pr2
            titanic = self.pr1

        if self.get_widget("name_btn1").get_active() ^ use_handle1:
            swapname = phoenix.get_primary_name()
            phoenix.set_primary_name(titanic.get_primary_name())
            titanic.set_primary_name(swapname)
        if self.get_widget("gender_btn1").get_active() ^ use_handle1:
            phoenix.set_gender(titanic.get_gender())
        if self.get_widget("gramps_btn1").get_active() ^ use_handle1:
            swapid = phoenix.get_gramps_id()
            phoenix.set_gramps_id(titanic.get_gramps_id())
            titanic.set_gramps_id(swapid)

        try:
            query = MergePersonQuery(self.database, phoenix, titanic)
            family_merge_ok = query.execute()
            if not family_merge_ok:
                WarningDialog(
                    _("Warning"),
                    _(
                        "The persons have been merged.\nHowever, the families "
                        "for this merge were too complex to automatically "
                        "handle.  We recommend that you go to Relationships "
                        "view and see if additional manual merging of families "
                        "is necessary."
                    ),
                    parent=self.window,
                )
            # Add the selected handle to history so that when merge is complete,
            # phoenix is the selected row.
            self.uistate.set_active(phoenix.get_handle(), "Person")
        except MergeError as err:
            ErrorDialog(_("Cannot merge people"), str(err), parent=self.window)
        self.uistate.set_busy_cursor(False)
        self.close()
        if self.update:
            self.update()


# ------------------------------------------------------------------------
#
#
#
# ------------------------------------------------------------------------
class Options(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {
            "soundex": 1,
            "threshold": 0.25,
            "date_tolerance": 0,
            "all_first_names": 0,
            "skip_no_surname": 0,
            "skip_no_birth_date": 0,
            "use_exclusions": 1,
            "random_percent": 100,
        }
        self.options_help = {
            "soundex": (
                "=0/1",
                "Whether to use SoundEx codes",
                ["Do not use SoundEx", "Use SoundEx"],
                True,
            ),
            "all_first_names": (
                "=0/1",
                "Whether to use all first name with comparisons",
                ["Do not use", "Use"],
                True,
            ),
            "skip_no_surname": (
                "=0/1",
                "Skip people with no surname",
                ["Do not use", "Use"],
                True,
            ),
            "skip_no_birth_date": (
                "=0/1",
                "Skip people with no birth date",
                ["Do not use", "Use"],
                True,
            ),
            "use_exclusions": (
                "=0/1",
                "Use_exclusions",
                ["Do not use", "Use"],
                True,
            ),
            "threshold": ("=num", "Threshold for tolerance", "Floating point number"),
            "date_tolerance": (
                "=num",
                "Threshold for date tolerance (number of years)",
                "Integer",
            ),
            "random_percent": (
                "=num",
                "Process randomly only a part of the database",
                "Integer",
            ),
            
        }

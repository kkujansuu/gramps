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

# This program uses the Whoosh library by Matt Chaput, see https://whoosh.readthedocs.io/en/latest/

import html
import os
import re
import shutil
import time
import traceback
import uuid

#import whoosh
import whoosh.highlight
from whoosh.index import create_in, open_dir
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import QueryParser
from whoosh.lang import morph_en
from whoosh.analysis import filters, StandardAnalyzer, RegexTokenizer, LowercaseFilter

from gi.repository import Gtk, Gdk

from gramps.gen.config import CONFIGMAN as gconfig
from gramps.gen.config import config as configman
from gramps.gen.const import GRAMPS_LOCALE as glocale

from gramps.gui.dialog import ErrorDialog, QuestionDialog
from gramps.gui.glade import Glade
from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter


import fulltext_objects
import fulltext_loader

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext



fulltext_config = configman.register_manager("fulltext")

fulltext_config.register("defaults.querytext", "")

class ColorFormatter(whoosh.highlight.Formatter):
    """
        Puts markup around the matched terms, see https://whoosh.readthedocs.io/en/latest/highlight.html#formatter
        Highlighting with color, see https://stackoverflow.com/questions/3629386/set-cellrenderertext-foreground-color-when-a-row-is-highlighted
    """

    PREFIX1 = "["+uuid.uuid4().hex+"["
    SUFFIX1 = "]"+uuid.uuid4().hex+"]"
    PREFIX2 = '<span foreground="red">'
    SUFFIX2 = '</span>'
    def format_token(self, text, token, replace=False):
        # Use the get_text function to get the text corresponding to the token
        tokentext = whoosh.highlight.get_text(text, token, replace)

        # Return the text as you want it to appear in the highlighted string
        return ColorFormatter.PREFIX1 + tokentext + ColorFormatter.SUFFIX1
        
# -------------------------------------------------------------------------
#
# Tool
#
# -------------------------------------------------------------------------
class Tool(tool.Tool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (Any, Any, Any, str, Callable) -> None
        self.user = user
        self.uistate = user.uistate
        self.dbstate = dbstate
        self.db = dbstate.db
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.engine = SearchEngine(dbstate)
        if user.uistate:
            self.run()


    def run(self):
        # type: () -> None
        self.glade = Glade(also_load=["liststore1"])
        self.query_field = self.glade.get_child_object("query")
        self.listmodel = self.glade.get_object("liststore1")
        self.listview = self.glade.get_object("listview")
        self.box1 = self.glade.get_child_object("box1")
        self.box2 = self.glade.get_child_object("box2")
        self.msg = self.glade.get_child_object("msg")
        self.msg2 = self.glade.get_child_object("msg2")
        self.create_index_button = self.glade.get_child_object("create_index")
        self.search_button = self.glade.get_child_object("search")
        self.grid = self.glade.get_child_object("grid")
        self.scrolledwindow = self.glade.get_child_object("scrolledwindow")
        self.object_types = self.glade.get_child_object("object_types")
        self.delete_index_button = self.glade.get_child_object("delete_index")
        self.build_index_button = self.glade.get_child_object("build_index")
        self.close_button = self.glade.get_child_object("close")
        self.limit = self.glade.get_child_object("limit")

        self.query_field.connect("key-press-event", self.keypress)
        self.search_button.connect("clicked", self.dosearch)
        self.create_index_button.connect("clicked", self.build_index2)
        self.listview.connect("button-press-event", self.button_press)

        self.delete_index_button.connect("clicked", self.do_delete_index)
        self.build_index_button.connect("clicked", self.build_index1)
        self.close_button.connect("clicked", lambda *args: self.glade.toplevel.destroy())

        self.dbstate.connect("database-changed", self.db_changed)

        cb = Gtk.CheckButton(label="All")
        cb.set_active(True)
        self.object_types.add(cb)
        cb.connect("toggled", self.set_checkboxes)
        self.checkbox_all = cb
        
        self.checkboxes = {}
        for col, objtype in enumerate(sorted(fulltext_objects.OBJTYPES), start=1):
            cb = Gtk.CheckButton(label=objtype)
            cb.set_active(True)
            self.object_types.add(cb)
            self.checkboxes[objtype] = cb
        self.object_types.show_all()
            
        fulltext_config.load()
        lastquery = fulltext_config.get("defaults.querytext")
        self.query_field.set_text(lastquery)
            

        self.msg.set_text("")
        if os.path.exists(self.engine.indexdir):
            self.box1.hide()
            self.box2.show_all()
            self.query_field.set_sensitive(True)
            self.search_button.set_sensitive(True)
            self.set_entry_completion()
            
        elif hasattr(self.db, "dbapi"):
            self.box1.show_all()
            self.box2.hide()
        else:
            self.box1.hide()
            self.box2.hide()
            self.scrolledwindow.hide()
            msg = "Fulltext search works only with SQLite databases"
            self.msg.set_text(msg)

        self.glade.toplevel.show()

    def set_entry_completion(self):
        self.completion_list = Gtk.ListStore(str)

        entry_completion = Gtk.EntryCompletion()
        entry_completion.set_inline_completion(True)
        entry_completion.set_inline_selection(True)
        entry_completion.set_text_column(0)

        entry_completion.set_model(self.completion_list)
        self.query_field.set_completion(entry_completion)

        try:
            words = open(self.engine.wordfile, encoding='utf-8').readlines()
        except:
            words = []
        
        self.completion_list.clear()
        for text in words:
            self.completion_list.append([text.strip()])
                    
    def db_changed(self, db):
        self.glade.toplevel.destroy()

    def set_checkboxes(self, _widget):
        value = self.checkbox_all.get_active()
        for cb in self.checkboxes.values():
            cb.set_active(value)
    
    def keypress(self, _obj, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.dosearch(None)

    def button_press(self, _treeview, event):
        # type: (Gtk.TreeView, Gtk.Event) -> bool
        if not self.db.db_is_open:
            return True
        try:  # may fail if clicked too frequently
            if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
                model, treeiter = self.listview.get_selection().get_selected()  # type: ignore
                row = list(model[treeiter])
                objtype = row[1]
                handle = row[3]
                proxy = fulltext_objects.getproxy(objtype)
                proxy.edit(self.dbstate, self.uistate, handle)

                return True
        except:
            traceback.print_exc()
        return False


    def do_delete_index(self, _widget):
        self.msg.set_text("")
        self.msg2.set_text("")
        QuestionDialog("Confirm delete","", "Delete index",  self.delete_index1)
        #self.delete_index()

    def delete_index1(self):
        self.engine.delete_index()
        self.box1.show_all()
        self.box2.hide()
        fulltext_loader.disable_trace(self.db)

    def build_index1(self, _widget):
        QuestionDialog("Confirm rebuild","", "Build",  self.build_index2)

    def build_index2(self, _widget=None):
        progress = ProgressMeter('Building index', 'Building', can_cancel=True)
        n, elapsed = self.engine.build_index(progress=progress)
        progress.close()
        msg = "Indexed {} objects in {:.2f} seconds".format(n, elapsed)
        self.set_entry_completion()
        self.msg.set_text(msg)
        self.msg2.set_text("")
        self.box1.hide()
        self.box2.show()

    def dosearch(self, _widget):
        query_text = self.query_field.get_text().strip()
        if query_text:
            fulltext_config.set("defaults.querytext", query_text)
            fulltext_config.save()

            types = []
            for objtype, cb in self.checkboxes.items():
                if cb.get_active():
                    types.append("objtype:"+objtype)
            if types and len(types) < len(self.checkboxes):
                s = " (" + " OR ".join(types) + ")"
            else:
                s = ""
            self.msg.set_text("")
            self.msg2.set_text("")
            rows, elapsed = self.engine.search(query_text + s, limit=int(self.limit.get_text()))
            self.listmodel.clear()
            for row in rows:
                self.listmodel.append(row)
            self.msg2.set_text("Results: {} (time {:.2f} s)".format(len(rows), elapsed))

class SearchEngine:
    def __init__(self, dbstate):
        self.dbstate = dbstate
        self.db = dbstate.db
        self.init_fulltext()
        
    def init_fulltext(self):
        dbpath = gconfig.get("database.path")
        dbid = self.db.get_dbid()
        if not dbid:
            ErrorDialog("Error", "Database is not open")
            return

        self.indexdir = os.path.join(dbpath, dbid, "indexdir")
        self.wordfile = self.indexdir + ".words"

        analyzer = RegexTokenizer(r"\w+|@|\$|£|€|#|=|\[|\]") | LowercaseFilter()
        self.schema = Schema(
            objtype=TEXT(stored=True),
            title=TEXT(stored=True),
            handle=ID(stored=True, unique=True),
            content=TEXT(analyzer=analyzer),
        )
        self.create_parser()

    def create_parser(self):
        self.parser = QueryParser("content", self.schema)
        self.parser.add_plugin(whoosh.qparser.FuzzyTermPlugin())
        self.parser.add_plugin(whoosh.qparser.PlusMinusPlugin())

    def delete_index(self):
        if os.path.exists(self.indexdir):
            shutil.rmtree(self.indexdir)
        if os.path.exists(self.wordfile):
            os.remove(self.wordfile)
        fulltext_loader.disable_trace(self.db)

    def build_index(self, _widget=None, progress=None):
        t1 = time.time()
        self.delete_index()
        os.makedirs(self.indexdir)
        ix = create_in(self.indexdir, self.schema)

        canceled = False
        n = 0
        words = set()
        with ix.writer() as writer:
            for objtype in sorted(fulltext_objects.OBJTYPES):
                print("-", objtype)
                if canceled: break
                proxy = fulltext_objects.getproxy(objtype)
                if progress:
                    progress.set_pass("Indexing: " + objtype, proxy.countfunc(self.db))
                print(proxy)
                print( proxy.iterfunc)
                print( proxy.iterfunc(self.db))
                for obj in proxy.iterfunc(self.db):
                    if progress and progress.step():
                        canceled = True
                        break
                    proxy.obj = obj
                    content=proxy.content(self.db)
                    if objtype== "personattr" and content:
                        print(">", content)
                    writer.add_document(
                        objtype=objtype,
                        title=proxy.gramps_id,
                        handle=proxy.handle,
                        content=content,
                    )
                    words.update(re.split(r"\W+", content))
                    n += 1

            with open(self.wordfile, "wt", encoding='utf-8') as f:
                for w in sorted(words):
                    print(w, file=f)
        
        fulltext_loader.enable_trace(self.db)
        t2 = time.time()
        return n, t2-t1

    def search(self, query_text, limit):
        t1 = time.time()
        ix = open_dir(self.indexdir)

        query = self.parser.parse(query_text)

        with ix.searcher() as searcher:
            results = searcher.search(query, limit=limit)
            results.formatter = whoosh.highlight.UppercaseFormatter()

            # Increase character limit
            results.fragmenter.charlimit = 100000
            
            # Allow larger fragments
            results.fragmenter.maxchars = 300

            # Show more context before and after
            results.fragmenter.surround = 50
            
            results.formatter = ColorFormatter()
            
            n = 0
            rows = []
            for res in results:
                objtype = res["objtype"]
                handle = res["handle"]
                proxy = fulltext_objects.getproxy(objtype)
                proxy.from_handle(self.db, handle)
                text = proxy.content_for_display(self.db)
                hltext = res.highlights("content", text=text)
                hltext2 = hltext.replace(ColorFormatter.PREFIX1, "").replace(ColorFormatter.SUFFIX1, "")
                if not text.startswith(hltext2): hltext = "..." + hltext

                hltext = html.escape(hltext)
                hltext = (hltext.replace(ColorFormatter.PREFIX1, ColorFormatter.PREFIX2)
                          .replace(ColorFormatter.SUFFIX1, ColorFormatter.SUFFIX2)) 

                rows.append([proxy.gramps_id, objtype, hltext, handle])
                n += 1
            t2 = time.time()
            return rows, t2-t1


# ------------------------------------------------------------------------
#
# Options
#
# ------------------------------------------------------------------------
class Options(tool.ToolOptions):
    pass
    
    

#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      KKu
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

#######################################################################
#
# DBTracer
#
# Tool to display database (SQL) calls in real time
#
#######################################################################

try:
    from typing import List, Tuple, Optional, Iterator, Generator, Any, Callable
except:
    pass
 
from gi.repository import Gtk

from gramps.gui.dialog import ErrorDialog
from gramps.gui.plug import tool

from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

import dbtrace

# import sqlite3
# sqlite3.enable_callback_tracebacks(True)

#######################################################################
#
# Tool
#
#######################################################################

class Tool(tool.Tool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (Any, Any, Any, str, Callable) -> None
        self.user = user
        self.uistate = user.uistate
        self.dbstate = dbstate
        tool.Tool.__init__(self, dbstate, options_class, name)

        self.callback_active = False
#        self.curdb = self.dbstate.db
        self.dbstate.connect("database-changed", self.db_changed)
        self.maindialog = self.createtracer()

    def db_changed(self, db):
        print("db_changed", db, db.get_dbid())
        if db.get_dbid() == "":
            return
        self.dbtrace_callback_key = dbtrace.enable_trace(db, self.tracer_callback)
            
            
    def createtracer(self):
        global tracer
        tracer = Gtk.Dialog()
        tracer.set_title("DBTracer")
        tracer.set_modal(False)
        self.but_enable = tracer.add_button("Enable trace", 1)
        self.but_disable = tracer.add_button("Disable trace", 2)
        self.but_clear = tracer.add_button("Clear", 3)
        tracer.add_button("Exit", 4)

        self.but_disable.set_sensitive(False)
        tracer.connect("response", self.tracer_handler)
        c = tracer.get_content_area()
        sw = Gtk.ScrolledWindow()
        sw.set_size_request(800, 800)
        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        sw.add(self.textview)
        self.textbuffer = self.textview.get_buffer()
        
        self.text = Gtk.Label()
        c.pack_start(sw, True, True, 0)
        c.add(self.text)
        self.count = 0

        db = self.dbstate.db            
        self.dbtrace_callback_key = dbtrace.enable_trace(db, self.tracer_callback)
        if self.dbtrace_callback_key is None:
            ErrorDialog("Error", "dbtrace.enable_trace failed")
            tracer.destroy()
            return
        self.callback_active = True
        self.but_enable.set_sensitive(False)
        self.but_disable.set_sensitive(True)

        tracer.show_all()
        return tracer
        
    def tracer_handler(self, widget, resp):
        db = self.dbstate.db            
        
        if resp == 1:
            self.dbtrace_callback_key = dbtrace.enable_trace(db, self.tracer_callback)
            if self.dbtrace_callback_key is None:
                ErrorDialog("Error", "dbtrace.enable_trace failed")
                widget.destroy()
            self.but_enable.set_sensitive(False)
            self.but_disable.set_sensitive(True)
            self.callback_active = True
        if resp == 2:
            dbtrace.disable_trace(db, self.dbtrace_callback_key)
            self.but_enable.set_sensitive(True)
            self.but_disable.set_sensitive(False)
            self.callback_active = False
        if resp == 3:
            self.textbuffer.set_text("")
            self.count = 0
            newlabel = f"Count = {self.count}"
            self.text.set_label(newlabel)
        if resp == 4:
            if self.callback_active:
                dbtrace.disable_trace(db, self.dbtrace_callback_key)
            widget.destroy()

    def tracer_callback(self, sqlstring):
        # print("sql", sqlstring)
        self.count += 1
        newlabel = f"Count = {self.count}"
        self.text.set_label(newlabel)

        end_iter = self.textbuffer.get_end_iter()
        self.textbuffer.insert(end_iter, sqlstring + "\n")

        # Scroll to the bottom
        mark = self.textbuffer.create_mark(None, end_iter, False)
        self.textview.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)



    
    
#######################################################################
#
# Options
#
#######################################################################

class Options(tool.ToolOptions):
    pass
    

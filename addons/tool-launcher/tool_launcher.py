#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024    Kari Kujansuu
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
# Foundation

import html
import importlib
import re
import traceback

from collections import defaultdict
from operator import attrgetter
from pprint import pprint

from gi.repository import Gtk

from gramps.gen.config import config as configman
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug import Gramplet
from gramps.gen.plug._pluginreg import PluginRegister, PTYPE, TOOL, TOOL_MODE_GUI

from gramps.gui.dialog import OkDialog
from gramps.gui.plug import tool
from gramps.gui.pluginmanager import GuiPluginManager
from gramps.gui.user import User

from gramps.version import major_version


try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

config = configman.register_manager("tool-launcher")
config.register("defaults.toollist", [])
config.register("defaults.closed_categories", [])

def all_plugins():
    pgr = PluginRegister.get_instance()
    for ptype in PTYPE:
        for pd in pgr.type_plugins(ptype):
            yield (ptype, pd)


class Launcher(Gramplet):

    def init(self):
        print("tool-launcher {}: init".format(id(self)))
        self.root = self.create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.root)
        self.set_tooltip(_("Launch a tool with one click"))

        self.populate_pluginsframe()
        self.populate_linkframe()

        pmgr = GuiPluginManager.get_instance()
        pmgr.connect("plugins-reloaded", self.plugins_reloaded)
        self.root.show_all()
        
    def plugins_reloaded(self):
        self.populate_pluginsframe()
        self.populate_linkframe()
        
    def create_gui(self):
        vbox = Gtk.VBox(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_spacing(0)

        self.linkframe = Gtk.Frame()
        vbox.pack_start(self.linkframe, False, True, 20)

        self.pluginsframe = Gtk.Frame()
        vbox.pack_start(self.pluginsframe, False, True, 20)
        return vbox
        
        
    def populate_linkframe(self):
        child = self.linkframe.get_child()
        if child:
            self.linkframe.remove(child)

        self.linkbox = Gtk.VBox()
        self.linkframe.add(self.linkbox)

        toollist = []
        for name, cb, pdata in sorted(self.items):
            if cb.get_active():
                toollist.append(pdata.id)
                lbl = Gtk.Label()
                lbl.set_markup('<a href="#">' + html.escape(name) + "</a>")
                lbl.set_halign(Gtk.Align.START)
                lbl.set_margin_top(10)
                lbl.set_margin_bottom(10)
                lbl.set_margin_left(10)
                lbl.pdata = pdata
                lbl.connect("button_press_event", self.run_tool) 
                self.linkbox.add(lbl)  
        self.linkframe.show_all()
        config.set("defaults.toollist", toollist)
        config.save()

    def populate_pluginsframe(self):
        child = self.pluginsframe.get_child()
        if child:
            self.pluginsframe.remove(child)

        categories = defaultdict(list)
        self.plugins = {}
        for ptype, pd in all_plugins():
            if ptype == TOOL and TOOL_MODE_GUI in pd.tool_modes:
                catname = tool.tool_categories[pd.category][1]
                pd.name_lower = pd.name.lower()
                categories[catname].append(pd)
                self.plugins[pd.id] = pd

        vbox = Gtk.VBox()

        config.load()
        toollist = config.get("defaults.toollist")
        closed_categories = config.get("defaults.closed_categories")
        self.expanders = []
        self.items = []
        
        for cat, pdlist in sorted(categories.items()):                
            exp = Gtk.Expander(label=cat)
            exp.set_margin_top(10)
            exp.set_resize_toplevel(True)
            exp.set_expanded(cat not in closed_categories)
            exp.connect("notify::expanded", self.expanders_changed)
           
            lbl = Gtk.Label()
            lbl.set_markup('<a href="#">' + cat + "</a>")
            store = Gtk.ListStore(bool,str, str)
            
            grid = Gtk.Grid()
            grid.set_row_spacing(2)
            
            for row, pd in enumerate(sorted(pdlist, key=attrgetter('name_lower'))):
                active = pd.id in toollist

                cb = Gtk.CheckButton()
                cb.set_margin_left(10)
                cb.pdata = pd
                cb.set_active(active)
                cb.connect("clicked", self.selected)
                
                lbl = Gtk.Label(pd.name)
                lbl.set_halign(Gtk.Align.START)
                lbl.set_margin_left(10)

                grid.attach(cb, 0, row, 1, 1)
                grid.attach(lbl, 1, row, 1, 1)

                self.items.append((pd.name, cb, pd))

            exp.add(grid)
            self.expanders.append(exp)
            vbox.add(exp)

        self.pluginsframe.add(vbox)
        vbox.show_all()
        return vbox

    def expanders_changed(self, expander, expanded):
        closed_categories = []
        for exp in self.expanders:
            if not exp.get_expanded():
                closed_categories.append(exp.get_label())
        config.set("defaults.closed_categories", closed_categories)
        config.save()
                
    def selected(self, widget):
        self.populate_linkframe()

    def run_tool(self, widget, event):
        pdata = widget.pdata
        pmgr = GuiPluginManager.get_instance()
        mod = pmgr.load_plugin(pdata)
        #importlib.reload(mod)
        tool.gui_tool(dbstate=self.dbstate, user=User(uistate=self.uistate),
                      tool_class=getattr(mod, pdata.toolclass),
                      options_class=getattr(mod, pdata.optionclass),
                      translated_name=pdata.name,
                      name=pdata.id,
                      category=pdata.category,
                      callback=self.dbstate.db.request_rebuild)


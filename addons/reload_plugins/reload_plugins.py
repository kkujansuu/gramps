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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import importlib
import os
import sys
import threading
import time
import traceback
from pprint import pprint

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.plug._pluginreg import PluginRegister, PTYPE

from gramps.gui.plug import tool
from gramps.gui.pluginmanager import GuiPluginManager

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

def all_plugins():
    pgr = PluginRegister.get_instance()
    for ptype in PTYPE:
        for pd in pgr.type_plugins(ptype):
            yield (ptype, pd)

def reload_plugin_modules():
    plugins = []
    for ptype, pd in all_plugins():
        modname = pd.fname[:-3]
        if modname in sys.modules:
            mod = sys.modules[modname] 
            spec = importlib.util.spec_from_file_location(modname, mod.__file__)            
            spec.loader.exec_module(mod)


def remove_duplicate_rules():
        namespaces = [
            "citation",
            "event",
            "family",
            "media",
            "note",
            "person",
            "place",
            "repository",
            "source",
        ]
        # remove duplicate rules
        # adapted from gramps.gen.plug._manager.reg_plugins()
        for namespace in namespaces:
            obj_rules = importlib.import_module(
                'gramps.gen.filters.rules.' + namespace)
            #from gramps.gen.filters.rules.person import editor_rule_list
            rules = {}
            for rule in obj_rules.editor_rule_list:
                key = (rule.category,rule.name)
                rules[key] = rule # newer rules will overrides older
            obj_rules.editor_rule_list[:] = rules.values()                

# -------------------------------------------------------------------------
#
# ReloadTool
#
# -------------------------------------------------------------------------


class ReloadTool(tool.Tool):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (Any, Any, Any, str, Callable) -> None
        tool.Tool.__init__(self, dbstate, options_class, name)
        
        if user.uistate: 
            user.uistate.viewmanager.do_reg_plugins(dbstate, user.uistate, rescan=True)
            user.uistate.uimanager.update_menu()

        reload_plugin_modules()  # Gramps 5.2 seems to require this !?
        remove_duplicate_rules() # rules are not reloaded 

        pmgr = GuiPluginManager.get_instance()
        pmgr.reload_plugins()
        pmgr.emit("plugins-reloaded")
                        
        curtime = time.strftime("%H:%M:%S", time.localtime(time.time()))
        msg = "Plugins reloaded at " + curtime
        print(msg) 
        if user.uistate:
            ctx_id = user.uistate.status.get_context_id("Reload plugins")
            msgid = user.uistate.status.push(ctx_id, msg)
            def remove_msg():
                time.sleep(3)
                msgid = user.uistate.status.push(ctx_id, "")
            t = threading.Thread(target=remove_msg)
            t.start()


# ------------------------------------------------------------------------
#
# ReloadOptions
#
# ------------------------------------------------------------------------
class ReloadOptions(tool.ToolOptions):
    pass


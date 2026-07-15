#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025-2026     Kari Kujansuu
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


import traceback
import os
import re
import textwrap

from collections import defaultdict
from gramps.plugins.export.exportxml import GrampsXmlWriter
from gramps.plugins.export.exportpkg import PackageWriter, writeData as gpkg_writeData
from gramps.gen.proxy.filter import FilterProxyDb
from gramps.gen.filters import CustomFilters, rules
from gramps.version import major_version
from gramps.gen.proxy.referencedbyselection import ReferencedBySelectionProxyDb
from gramps.plugins.export.exportgedcom import GedcomWriter
from gramps.gen.filters._genericfilter import GenericFilter


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

from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext



#-------------------------------------------------------------------------
#
# Tool
#
#-------------------------------------------------------------------------
class Tool(tool.Tool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        # type: (Any, Any, Any, str, Callable) -> None
        self.user = user
        self.uistate = user.uistate
        self.dbstate = dbstate
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.run()

    def run(self):
        # type: () -> None
        filename =  self.options.handler.options_dict['filename']
        filtername =  self.options.handler.options_dict['filter']
        gramps_id =  self.options.handler.options_dict['gramps_id']
        db = self.dbstate.db 
        if filtername:
            filter = None
            if gramps_id:
                filter = self.get_filter(filtername,gramps_id)
                if filter:
                    print(filter.name)
                    db = FilterProxyDb(db, filter, user=self.user)
                else:
                    raise RuntimeError(textwrap.dedent(f"""
                    If gramps_id is specified then filtername must be one of:
                        * descendants
                        * descendant_families
                        * ancestors
                        * common_ancestor
                    """))
            if not filter:
                CustomFilters.load()
                category = "Person"
                filters = CustomFilters.get_filters_dict(category)
                if filtername in filters:
                    print(f"Filter '{filtername}' found")
                    filter = filters[filtername]
                    db = FilterProxyDb(db, filter, user=self.user)
                else:
                    raise RuntimeError(f"Filter '{filtername}' not found")
        db = ReferencedBySelectionProxyDb(db, all_people=True)
        
        if filename.endswith(".gramps"):
            writer = GrampsXmlWriter(db, compress=0, version=major_version, user=self.user)
            filename = os.path.abspath(filename)
            writer.write(filename)        
        elif filename.endswith(".gpkg"):
            filename = os.path.abspath(filename)
            writer = PackageWriter(db, filename, self.user)
            writer.export()        
            #gpkg_writeData(db, filename, self.user, option_box=None)
        elif filename.endswith(".ged"):
            writer = GedcomWriter(db, self.user)
            writer.write_gedcom_file(filename)
        else:
            raise RuntimeError("Type must be 'gedcom' or 'gramps'")

    def get_filter(self, filtername, gramps_id):
        print("filter:", filtername)
        person = self.dbstate.db.get_person_from_gramps_id(gramps_id)
        if not person:
            raise RuntimeError(f"Person with id {gramps_id}' not found")
        person_name = name_displayer.display(person)
        print("person:", person_name)

        if filtername == "descendants":
            des = GenericFilter()
            # feature request 2356: avoid genitive form
            des.set_name(_("Descendants of %s") % person_name)
            des.add_rule(rules.person.IsDescendantOf([gramps_id, 1]))
            return des

        if filtername == "descendant_families":
            df = GenericFilter()
            # feature request 2356: avoid genitive form
            df.set_name(_("Descendant Families of %s") % person_name)
            df.add_rule(rules.person.IsDescendantFamilyOf([gramps_id, 1]))
            return df

        if filtername == "ancestors":
            ans = GenericFilter()
            # feature request 2356: avoid genitive form
            ans.set_name(_("Ancestors of %s") % person_name)
            ans.add_rule(rules.person.IsAncestorOf([gramps_id, 1]))
            return ans

        if filtername == "common_ancestor":
            com = GenericFilter()
            com.set_name(_("People with common ancestor with %s") % person_name)
            com.add_rule(rules.person.HasCommonAncestorWith([gramps_id]))
            return com
    
        return None
        


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
            filename 	= "",
            filter      = "",
            gramps_id    = "",
        )
        self.options_help = dict(
            filename 	=  ("=str","Output file",
                           "String"),
            filter      =  ("=str","Filter name",
                           "String"),
            gramps_id    =  ("=str","Gramps id",
                           "String"),
        )


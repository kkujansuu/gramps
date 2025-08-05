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

import logging
import os
import pickle
import pprint
import re
import shutil
import sys
import traceback

try:
    import orjson   # only in 6.0+
except:
    pass

from whoosh.index import open_dir

from gramps.gen.config import CONFIGMAN as config
from gramps.gen.lib import Note
from gramps.gen.lib import Person
from gramps.gen.lib import Event

from gramps.gui.dbman import DbManager
from gramps.gui.editors import EditCitation
from gramps.gui.editors import EditEvent
from gramps.gui.editors import EditFamily
from gramps.gui.editors import EditMedia
from gramps.gui.editors import EditNote
from gramps.gui.editors import EditPerson
from gramps.gui.editors import EditPlace
from gramps.gui.editors import EditRepository
from gramps.gui.editors import EditSource

dbpath = config.get("database.path")

import fulltext_objects

LOG = logging.getLogger(".fulltext")

def load_on_reg(dbstate, uistate, plugin):
    if "fulltext_marker" in sys.modules: # to avoid doing the dbstate.connect below multiple times if plugins are reloaded
        #print("already loaded")
        return
    dirname = os.path.split(__file__)[0]
    sys.path.append(dirname)
    import fulltext_marker
    import whoosh

    dbstate.connect("database-changed", db_changed)

    if not hasattr(DbManager, "orig_really_delete_db"):
        DbManager.orig_really_delete_db = DbManager._DbManager__really_delete_db
    DbManager._DbManager__really_delete_db = really_delete_db

def really_delete_db(self):
    directory = self.data_to_delete[1]
    indexdir = os.path.join(directory, "indexdir")
    if os.path.exists(indexdir):
        shutil.rmtree(indexdir)
    DbManager.orig_really_delete_db(self)


def db_changed(db):
    dbid = db.get_dbid()
    if dbid == "":
        return
    indexdir = os.path.join(dbpath, dbid, "indexdir")
    if os.path.exists(indexdir):
        print(indexdir, "exists", db.get_dbname())
        enable_trace(db)
    else:
        print(indexdir, "does not exist", db.get_dbname())
        pass

def enable_trace(db):
    import dbtrace
    db.fulltext_dbtrace_callback_key = dbtrace.enable_trace(db, lambda sqlstring: callback(db, sqlstring))

def disable_trace(db):
    import dbtrace
    if hasattr(db, "fulltext_dbtrace_callback_key"):
        dbtrace.disable_trace(db, db.fulltext_dbtrace_callback_key)
        del db.fulltext_dbtrace_callback_key

def callback(db, sqlstring):
    # print(sqlstring)
    if sqlstring.startswith("SELECT "):
        return
    
    if re.match(r"INSERT INTO \w+ \(handle, blob_data\) VALUES",  sqlstring):
        # INSERT INTO note (handle, blob_data) VALUES ('fa58e755a2176eb0842bba649f3', x'800495...')
        # print(sqlstring)
        
        objtype = sqlstring.split()[2]
        if objtype not in fulltext_objects.OBJTYPES:
            return
        hexdata = sqlstring.split()[7][2:-2]
        proxy = fulltext_objects.getproxy(objtype)
        proxy.from_hexdata(hexdata)
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            for seq, (contenttype, content) in enumerate(proxy.content()):
                writer.add_document(
                    objtype=objtype,
                    title=proxy.gramps_id,
                    handle=proxy.handle,
                    seq=seq,
                    contenttype=contenttype,
                    content=content,
                )

    if re.match(r"UPDATE \w+ SET blob_data = ",  sqlstring):
        # print(sqlstring)
        # UPDATE note SET blob_data = x'800495cd...' WHERE handle = 'f9e7c3ae9d734e31b1879b0bc4c'
        #
        objtype = sqlstring.split()[1]
        if objtype not in fulltext_objects.OBJTYPES:
            return
        hexdata = sqlstring.split()[5][2:-1]
        proxy = fulltext_objects.getproxy(objtype)
        proxy.from_hexdata(hexdata)
        # print(sqlstring)
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            writer.delete_by_term('handle', proxy.handle)
            for seq, (contenttype, content) in enumerate(proxy.content()):
                writer.add_document(
                    objtype=objtype,
                    title=proxy.gramps_id,
                    handle=proxy.handle,
                    seq=seq,
                    contenttype=contenttype,
                    content=content,
                )
            # print("-", objtype, proxy.gramps_id, repr(proxy.handle), repr(proxy.content))

    if re.match(r"INSERT INTO \w+ \(handle, json_data\) VALUES",  sqlstring):
        # INSERT INTO person (handle, json_data) VALUES ('ff35452da6668a80f91bb708dfb',
        # '{"handle":"ff35452da6668a80f91bb708dfb",
        #    "change":1753733247,"private":false,"tag_list":[],"gramps_id":"I1959",
        #    "citation_list":["c140d24888745dd09d7"],"note_list":[],"media_list":[],
        #    "event_ref_list":[],"attribute_list":[],"address_list":[],"urls":[],
        #    "lds_ord_list":[],"primary_name":{"private":false,
        #    "surname_list":[{"surname":"Warner","prefix":"","primary":true,
        #    "origintype":{"_class":"NameOriginType","value":1,"string":""},
        #    "connector":"","_class":"Surname"}],"citation_list":[],
        #    "note_list":[],"date":{"format":null,"calendar":0,"modifier":0,
        #    "quality":0,"dateval":[0,0,0,false],"text":"","sortval":0,
        #    "newyear":0,"_class":"Date"},"first_name":"Robert","suffix":"",
        #    "title":"","type":{"_class":"NameType","value":2,"string":""},
        #    "group_as":"","sort_as":0,"display_as":0,"call":"","nick":"",
        #    "famnick":"","_class":"Name"},"family_list":["B2WKQCNO586QCPVZ9S"],
        #    "parent_family_list":["OAAKQCZC8HVYD3C3JA"],"alternate_names":[],
        #    "person_ref_list":[],"death_ref_index":-1,
        #     "birth_ref_index":-1,"_class":"Person","gender":1}' 
        print(sqlstring)
        objtype = sqlstring.split()[2]
        if objtype not in fulltext_objects.OBJTYPES:
            return

        i = sqlstring.find("'")
        i = sqlstring.find("'", i+1)
        i = sqlstring.find("'", i+1)
        j = sqlstring.rfind("'")
        jsonstring = sqlstring[i+1:j]
        LOG.info("INSERT INTO " + objtype + "\n" + pprint.pformat(orjson.loads(jsonstring)))
        proxy = fulltext_objects.getproxy(objtype)
        proxy.from_jsonstring(jsonstring)
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            for seq, (contenttype, content) in enumerate(proxy.content()):
                writer.add_document(
                    objtype=objtype,
                    title=proxy.gramps_id,
                    handle=proxy.handle,
                    seq=seq,
                    contenttype=contenttype,
                    content=content,
                )


    if re.match(r"UPDATE \w+ SET json_data = ",  sqlstring):
        # UPDATE person SET json_data = '{"handle":"22WKQC0LKX6LZD83VP",
        #    "change":1753733247,"private":false,"tag_list":[],"gramps_id":"I1959",
        #    "citation_list":["c140d24888745dd09d7"],"note_list":[],"media_list":[],
        #    "event_ref_list":[],"attribute_list":[],"address_list":[],"urls":[],
        #    "lds_ord_list":[],"primary_name":{"private":false,
        #    "surname_list":[{"surname":"Warner","prefix":"","primary":true,
        #    "origintype":{"_class":"NameOriginType","value":1,"string":""},
        #    "connector":"","_class":"Surname"}],"citation_list":[],
        #    "note_list":[],"date":{"format":null,"calendar":0,"modifier":0,
        #    "quality":0,"dateval":[0,0,0,false],"text":"","sortval":0,
        #    "newyear":0,"_class":"Date"},"first_name":"Robert","suffix":"",
        #    "title":"","type":{"_class":"NameType","value":2,"string":""},
        #    "group_as":"","sort_as":0,"display_as":0,"call":"","nick":"",
        #    "famnick":"","_class":"Name"},"family_list":["B2WKQCNO586QCPVZ9S"],
        #    "parent_family_list":["OAAKQCZC8HVYD3C3JA"],"alternate_names":[],
        #    "person_ref_list":[],"death_ref_index":-1,
        #     "birth_ref_index":-1,"_class":"Person","gender":1}' 
        # WHERE handle = '22WKQC0LKX6LZD83VP'
        
        objtype = sqlstring.split()[1]
        if objtype not in fulltext_objects.OBJTYPES:
            return
        i = sqlstring.find("'")
        j = sqlstring.rfind("'")
        j = sqlstring.rfind("'", 0, j)
        j = sqlstring.rfind("'", 0, j)
        jsonstring = sqlstring[i+1:j]
        LOG.info("UPDATE " + objtype + "\n" + pprint.pformat(orjson.loads(jsonstring)))
        proxy = fulltext_objects.getproxy(objtype)
        proxy.from_jsonstring(jsonstring)
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            writer.delete_by_term('handle', proxy.handle)
            for seq, (contenttype, content) in enumerate(proxy.content()):
                writer.add_document(
                    objtype=objtype,
                    title=proxy.gramps_id,
                    handle=proxy.handle,
                    seq=seq,
                    contenttype=contenttype,
                    content=content,
                )

    if sqlstring.startswith("DELETE FROM "):
        # DELETE FROM note WHERE handle = 'fa58e755a2176eb0842bba649f3'
        # Works for both blob and json data
        objtype = sqlstring.split()[2]
        if objtype not in fulltext_objects.OBJTYPES:
            return
        handle = sqlstring.split()[-1][1:-1]
        LOG.info(sqlstring)
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            writer.delete_by_term("handle", handle)


def get_ix(db):
    dbid = db.get_dbid()
    indexdir = os.path.join(dbpath, dbid, "indexdir")
    try:
        ix = open_dir(indexdir)
    except:
        traceback.print_exc()
        if not os.path.exists(indexdir): # index as been deleted
            disable_trace(db)
        return None
    return ix

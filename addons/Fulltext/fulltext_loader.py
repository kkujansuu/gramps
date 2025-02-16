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

import os
import pickle
import shutil
import sys
import traceback

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
        #print(indexdir, "exists", db.get_dbname())
        enable_trace(db)
    else:
        #print(indexdir, "does not exist", db.get_dbname())
        pass


def enable_trace(db):
    connection = db.dbapi._Connection__connection
    connection.set_trace_callback(lambda sqlstring: callback(db, sqlstring))

def disable_trace(db):
    connection = db.dbapi._Connection__connection
    connection.set_trace_callback(None)

def callback(db, sqlstring):
    if sqlstring.startswith("INSERT INTO ") and "blob_data" in sqlstring:
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
            for seq, (contenttype, content) in enumerate(proxy.content(db)):
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
        # print(sqlstring)
        objtype = sqlstring.split()[2]
        if objtype not in fulltext_objects.OBJTYPES:
            return
        handle = sqlstring.split()[-1][1:-1]
        ix = get_ix(db)
        if ix is None: return
        with ix.writer() as writer:
            writer.delete_by_term("handle", handle)

    if sqlstring.startswith("UPDATE ") and "blob_data" in sqlstring:
        # print(sqlstring)
        # UPDATE note SET blob_data = x'800495cd...' WHERE handle = 'f9e7c3ae9d734e31b1879b0bc4c'
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
            for seq, (contenttype, content) in enumerate(proxy.content(db)):
                writer.add_document(
                    objtype=objtype,
                    title=proxy.gramps_id,
                    handle=proxy.handle,
                    seq=seq,
                    contenttype=contenttype,
                    content=content,
                )
            # print("-", objtype, proxy.gramps_id, repr(proxy.handle), repr(proxy.content))


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

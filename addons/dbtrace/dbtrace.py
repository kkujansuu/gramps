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
import sys
import time
import traceback
import sqlite3
import uuid

from collections import defaultdict
from contextlib import contextmanager 
from pprint import pprint

from gramps.gui.dialog import ErrorDialog

def load_on_reg(dbstate, uistate, plugin):
    if hasattr(sys, "dbtrace_callbacks"): # to avoid doing the dbstate.connect below multiple times if plugins are reloaded
        # print("dbtrace already loaded")
        return
    sys.dbtrace_callbacks = dict()
    dbstate.connect("database-changed", db_changed)

def db_changed(db):
    dbid = db.get_dbid()
    if dbid == "":
        sys.dbtrace_callbacks = dict()

@contextmanager 
def tracing(db, callback):
    key = enable_trace(db, callback)
    try:
        yield
    finally:
        disable_trace(db, key)

def enable_trace(db, callback):
    try:
        import fulltext
        if not hasattr(fulltext, "dbtrace_version"):
            ErrorDialog("Error", "The dbtrace module does not work with the Fulltext tool with version < 0.9.4")
            return
    except:
        pass

    dbid = db.get_dbid()
    if dbid == "":
        return
    key = uuid.uuid4().hex
    activate_trace(db)
    sys.dbtrace_callbacks[key] = callback
    # pprint(sys.dbtrace_callbacks)
    return key

def disable_trace(db, key):
    dbid = db.get_dbid()
    if dbid == "":
        return
    if key in sys.dbtrace_callbacks:
        del sys.dbtrace_callbacks[key]
    if not sys.dbtrace_callbacks: # empty
        connection = db.dbapi._Connection__connection
        connection.set_trace_callback(None)  # disable any tracing

def activate_trace(db):
    dbid = db.get_dbid()
    connection = db.dbapi._Connection__connection
    connection.set_trace_callback(lambda sqlstring: dbtrace_callback(dbid, sqlstring))
        
def dbtrace_callback(dbid, sqlstring):
    for cb in sys.dbtrace_callbacks.values():
        cb(sqlstring) 
    

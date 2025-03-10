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
import traceback

from gramps.gen.config import CONFIGMAN as config

from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer

from gramps.gen.lib import Citation
from gramps.gen.lib import Event
from gramps.gen.lib import Family
from gramps.gen.lib import Media
from gramps.gen.lib import Note
from gramps.gen.lib import Person
from gramps.gen.lib import Place
from gramps.gen.lib import Repository
from gramps.gen.lib import Source

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

class ProxyBase:
    @property
    def handle(self):
        return self.obj.handle

    @property
    def gramps_id(self):
        return self.obj.gramps_id

    def from_hexdata(self, hexdata):
        pickled = bytes.fromhex(hexdata)
        data = pickle.loads(pickled)
        self.obj.unserialize(data)

    def content_for_display(self, db, contenttype, seq):
        (ctype, content) = list(self.content())[seq]
        return content

    def process_attributes(self):
        for attr in self.obj.attribute_list:
            name = str(attr.type) + " = " + attr.value
            yield ("attr",  name)

    def process_urls(self):
        for url in self.obj.urls:
            if url.desc:
                name = url.path + " (" + url.desc + ")"
            else:
                name = url.path
            yield ("url", name)


class NoteProxy(ProxyBase):
    def __init__(self):
        self.obj = Note()

    def iterfunc(self, db):
        return db.iter_notes()

    def countfunc(self, db):
        return db.get_number_of_notes()

    def content(self):
        yield ("text", str(self.obj.text).replace("\n", " "))

    def from_handle(self, db, handle):
        self.obj = db.get_note_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditNote(dbstate, uistate, track, self.obj)


class PersonProxy(ProxyBase ):
    def __init__(self):
        self.obj = Person()

    def iterfunc(self, db):
        return db.iter_people()

    def countfunc(self, db):
        return db.get_number_of_people()

    def content(self):
        contenttype = "name"
        for name in [self.obj.primary_name] + self.obj.alternate_names:
            # name formatted like 'regular_name' but nickname is added after first name
            first = name.first_name
            surname = name.get_surname()
            nick = name.get_nick_name()
            if nick:
                first += f" ({nick})"
            if name.suffix == "":
                fullname = "%s %s" % (first, surname)
            else:
                fullname = "%(first)s %(surname)s, %(suffix)s" % {
                    "surname": surname,
                    "first": first,
                    "suffix": name.suffix,
                }
                
            yield (contenttype, fullname)
            contenttype = "altname"

        yield from self.process_attributes()
        yield from self.process_urls()         

    def from_handle(self, db, handle):
        self.obj = db.get_person_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditPerson(dbstate, uistate, track, self.obj)


class EventProxy(ProxyBase):
    def __init__(self):
        self.obj = Event()

    def iterfunc(self, db):
        return db.iter_events()

    def countfunc(self, db):
        return db.get_number_of_events()

    def content(self):
        yield ("description", self.obj.description)
        yield from self.process_attributes()

    def from_handle(self, db, handle):
        self.obj = db.get_event_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditEvent(dbstate, uistate, track, self.obj)


class PlaceProxy(ProxyBase):
    def __init__(self):
        self.obj = Place()

    def iterfunc(self, db):
        return db.iter_places()

    def countfunc(self, db):
        return db.get_number_of_places()

    def content(self):
        yield ("name", self.obj.get_name().get_value())
        for pn in self.obj.get_alternative_names():
            yield ("altname", pn.get_value())
        yield from self.process_urls()         

    def content_for_display(self, db, contenttype, seq):
        if contenttype == "name":
            names = [place_displayer.display(db, self.obj)] 
            for pn in self.obj.get_alternative_names():
                names.append(pn.get_value())
            return " / ".join(names)
        return super().content_for_display(db, contenttype, seq)

    def from_handle(self, db, handle):
        self.obj = db.get_place_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditPlace(dbstate, uistate, track, self.obj)

class CitationProxy(ProxyBase):
    def __init__(self):
        self.obj = Citation()

    def iterfunc(self, db):
        return db.iter_citations()

    def countfunc(self, db):
        return db.get_number_of_citations()

    def content(self):
        yield ("page", self.obj.get_page())
        yield from self.process_attributes()

    def from_handle(self, db, handle):
        self.obj = db.get_citation_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditCitation(dbstate, uistate, track, self.obj)


class SourceProxy(ProxyBase):
    def __init__(self):
        self.obj = Source()

    def iterfunc(self, db):
        return db.iter_sources()

    def countfunc(self, db):
        return db.get_number_of_sources()

    def content(self):
        yield ("title", self.obj.get_title())
        yield ("author", self.obj.get_author())
        yield from self.process_attributes()

    def from_handle(self, db, handle):
        self.obj = db.get_source_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditSource(dbstate, uistate, track, self.obj)

class RepositoryProxy(ProxyBase):
    def __init__(self):
        self.obj = Repository()

    def iterfunc(self, db):
        return db.iter_repositories()

    def countfunc(self, db):
        return db.get_number_of_repositories()

    def content(self):
        yield ("name", self.obj.get_name())
        yield from self.process_urls()         

    def from_handle(self, db, handle):
        self.obj = db.get_repository_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditRepository(dbstate, uistate, track, self.obj)


class MediaProxy(ProxyBase):
    def __init__(self):
        self.obj = Media()

    def iterfunc(self, db):
        return db.iter_media()

    def countfunc(self, db):
        return db.get_number_of_media()

    def content(self):
        yield ("description", self.obj.get_description())
        yield from self.process_attributes()

    def from_handle(self, db, handle):
        self.obj = db.get_media_from_handle(handle)

    def edit(self, dbstate, uistate, handle, track):
        self.from_handle(dbstate.db, handle)
        EditMedia(dbstate, uistate, track, self.obj)

OBJTYPES = {
    "note": NoteProxy,
    "person": PersonProxy, 
    "event": EventProxy,
    "place": PlaceProxy,
    "source": SourceProxy,
    "citation": CitationProxy,
    "repository": RepositoryProxy,
    "media": MediaProxy,
}


def getproxy(objtype):
    proxyclass = OBJTYPES.get(objtype)
    return proxyclass()



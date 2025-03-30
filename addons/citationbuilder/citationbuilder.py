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

# Citation Builder
# ================
# Tries to generate a citation, source and repository from a string given in citation vol/page field of the citation editor.
# The string should be of a specific format, one of the formats defined in matcher_module.py.
#


# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
import importlib
import os
import sys
import time
import traceback

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.lib import Date, Source, Repository, RepoRef, RepositoryType, Note, NoteType
from gramps.gui.editors import EditCitation
from gramps.gui.dialog import ErrorDialog

from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

import matcher_module as matcher


def load_on_reg(dbstate, uistate, plugin):
    orig_funcname = "orig_save_for_{}".format(plugin.id)
    if not hasattr(EditCitation, orig_funcname):
        setattr(EditCitation, orig_funcname, EditCitation.save)
    orig_save = getattr(EditCitation, orig_funcname)
    EditCitation.save = lambda self, *args: new_save(self, orig_save, *args)


def new_save(self, orig_save, _w):
    """
    This replaces EditCitation.save.
    First check if a source has been selected. If not, then check if the vol/page value matches a known pattern.
    If there is a match then proceed to add the corresponding citation, source and repository. However, if there already
    exists a matching citation then do not add a new one but use the existing citation.
    """
    if not self.obj.get_reference_handle():  # no Source attached for a new citation
        m = matcher.matches(self.obj.page)
        if m:
            existing_citation = add_source_to_citation(m, self.obj, self.db)
            if existing_citation:
                self.obj = existing_citation
        else:
            ErrorDialog(
                _("Warning"),
                _(
                    "The source is not defined but the Volume/Page field does not match any supported format"
                ),
            )
    orig_save(self)


def add_source_to_citation(m, citation, db):
    with DbTxn(_("Build a citation"), db) as trans:

        source = find_source(m.sourcetitle, db, trans)
        existing_citation = find_existing_citation(
            db, m.citationpage, m.details, source.handle
        )
        if existing_citation:
            return existing_citation

        repo = find_repo(m.reponame, db, trans)

        citation.set_page(m.citationpage)
        citation.set_reference_handle(source.handle)

        date = time.strftime("%d.%m.%Y", time.localtime(time.time()))
        date = time.localtime(time.time())
        dt = Date(date.tm_year, date.tm_mon, date.tm_mday)
#        strdate = str(Date(date.tm_year, date.tm_mon, date-tm_day))
        from gramps.gen.datehandler import format_time, displayer
        strdate = displayer.display(dt)
        newnote = Note()
        newnote.set(f"{m.details} / {_('Retrieved')} {strdate}")
        print(newnote.get())
        newnote.set_type(NoteType.CITATION)
        db.add_note(newnote, trans)

        citation.add_note(newnote.handle)

        if repo and not source.has_repo_reference(repo.handle):
            reporef = RepoRef()
            reporef.set_reference_handle(repo.handle)
            source.add_repo_reference(reporef)
            db.commit_source(source, trans)


def find_existing_citation(db, citationpage, notetext, sourcehandle):
    """Find a matching citation"""
    for citation in db.iter_citations():
        if (
            citation.handle
            and citation.page == citationpage
            and citation.source_handle == sourcehandle
        ):
            for notehandle in citation.get_note_list():
                note = db.get_note_from_handle(notehandle)
                if note.get() == notetext or links_match(note.get(), notetext):
                    return citation
    return None


def links_match(text1, text2):
    print("links match")
    print("-", text1)
    print("-", text2)
    url1 = find_url(text1)
    if url1 is None:
        return False
    url2 = find_url(text2)
    if url2 is None:
        return False
    return url1 == url2


def find_url(text):
    i = text.find("https://")
    if i >= 0:
        return text[i:].split()[0]
    i = text.find("http://")
    if i >= 0:
        return text[i:].split()[0]
    return None


def find_source(sourcetitle, db, trans):
    for source in db.iter_sources():
        if source.title == sourcetitle:
            return source
    source = Source()
    source.set_title(sourcetitle)
    db.add_source(source, trans)
    return source


def find_repo(reponame, db, trans):
    if reponame == "":
        return None
    for repo in db.iter_repositories():
        if repo.name == reponame:
            return repo
    repo = Repository()
    repo.set_type(RepositoryType.ARCHIVE)
    repo.set_name(reponame)
    db.add_repository(repo, trans)
    return repo

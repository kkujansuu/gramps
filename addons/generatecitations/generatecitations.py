#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Nick Hall
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
# generatecitations.py: 2018-2019 kari.kujansuu@gmail.com

"""Tools/Database Processing/Generate citations from event notes"""
from collections import defaultdict
import pprint
import re
import time
import traceback

from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter
from gramps.gui.dialog import OkDialog
from gramps.gen.db import DbTxn
from gramps.gen.lib import Citation, Source, Repository, RepoRef, Note, NoteType, Person, Family, Event, Place, Media, Tag
from gramps.gen.lib.notebase import NoteBase
from gramps.gen.lib.citationbase import CitationBase
from gramps.gen.const import GRAMPS_LOCALE as glocale
#_ = glocale.translation.gettext

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

#--------------------------------------------------
#
# GenerateCitations 
#
#-------------------------------------------------------------------------

            
def maketitle(reponame,sourcetitle):
    if reponame.endswith("seurakunnan arkisto"):
        return reponame.replace(" arkisto"," ") + sourcetitle[0].lower() + sourcetitle[1:]
    if reponame.endswith("församlings arkiv"):
        return reponame.replace(" arkiv"," ") + sourcetitle[0].lower() + sourcetitle[1:]
    return "{} - {}".format(reponame,sourcetitle)

class Match:
    def __init__(self, line,reponame,sourcetitle,citationpage,details,url,date):
        self.line = line
        self.reponame = reponame
        self.sourcetitle = sourcetitle
        self.citationpage = citationpage
        self.details = details
        self.url = url
        self.date = date

class GenerateCitations(tool.BatchTool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        self.user = user
        self.dbstate = dbstate
        self.uistate = user.uistate
        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        self.total_notes = 0

        self.regex_narc = re.compile("(.+?) - (.+?), jakso (.+); Kansallisarkisto: (.+) / Viitattu (.+)")  # now I have two problems

        # modified from /usr/lib/python3/dist-packages/gramps/plugins/db/bsddb/read.py
        self.primary_objects = {
            'Person': {
                'iter_func': self.db.iter_people,
                'commit_func': self.db.commit_person,
                'class_func': Person,
                },
            'Family': {
                'iter_func': self.db.iter_families,
                'commit_func': self.db.commit_family,
                'class_func': Family,
                },
            'Event': {
                'iter_func': self.db.iter_events,
                'commit_func': self.db.commit_event,
                'class_func': Event,
                },
            'Place': {
                'iter_func': self.db.iter_places,
                'commit_func': self.db.commit_place,
                'class_func': Place,
                },
            'Source': {
                'iter_func': self.db.iter_sources,
                'commit_func': self.db.commit_source,
                'class_func': Source,
                },
            'Citation': {
                'iter_func': self.db.iter_citations,
                'commit_func': self.db.commit_citation,
                'class_func': Citation,
                },
            'Media': {
                'iter_func': self.db.iter_media,
                'commit_func': self.db.commit_media,
                'class_func': Media,
                },
            'Repository': {
                'iter_func': self.db.iter_repositories,
                'commit_func': self.db.commit_repository,
                'class_func': Repository,
                },
            'Note':   {
                'iter_func': self.db.iter_notes,
                'commit_func': self.db.commit_note,
                'class_func': Note,
                },
            'Tag':   {
                'iter_func': self.db.iter_tags,
                'commit_func': self.db.commit_tag,
                'class_func': Tag,
                },
        }
        
        self.msgs = []
        try:
            self.run()
        except:
            msg = traceback.format_exc()
            msg += "\n".join(self.msgs)
            print(msg)
            OkDialog(_("Error occurred, please report this message:"),
                     msg,
                     parent=self.uistate.window)
            

    def log(self,msg):
        self.msgs.append(msg)
        print(msg)

    def match(self,note):
        notelines = note.get().splitlines()
        if len(notelines) == 0: return None
        return self.matchline(notelines)

    def matchline(self,notelines):
        line = notelines[0]
        m = self.match_narc(line)
        if m: return m
        m = self.match_sshy(line)
        if m: return m
        m = self.match_svar(line)
        if m: return m
        m = self.match_kansalliskirjasto(notelines)
        if m: return m
        return None
        
    def match_narc(self,line):
# Liperin seurakunnan arkisto - Syntyneiden ja kastettujen luettelot 1772-1811 (I C:3), jakso 3: kastetut 1772 tammikuu; Kansallisarkisto: http://digi.narc.fi/digi/view.ka?kuid=6593368 / Viitattu 22.10.2018
        m = self.regex_narc.match(line)
        if not m: return None
        reponame = m.group(1)            
        sourcetitle = maketitle(reponame,m.group(2))
        citationpage = "jakso " + m.group(3)
        url = m.group(4)
        date = m.group(5)
        details = "Kansallisarkisto: {} / Viitattu {}".format(url,date)
        return Match(line,reponame,sourcetitle,citationpage,details,url,date)

    def match_sshy(self,line):
# Tampereen tuomiokirkkoseurakunta - rippikirja, 1878-1887 (MKO166-181 I Aa:17) > 39: Clayhills tjenstespersoner; SSHY: http://www.sukuhistoria.fi/sshy/sivut/jasenille/paikat.php?bid=18233&pnum=39 / Viitattu 6.11.2018
        regex_sshy = re.compile("(.+) - (.+) > (.+): (.*); SSHY: (.+) / Viitattu (.+)")  # now I have two problems
        m = regex_sshy.match(line)
        if not m: return None
        reponame = m.group(1)            
        sourcetitle = "{} {}".format(reponame,m.group(2))
        desc = m.group(4).strip()
        if desc:
            citationpage = "kuva {}: {}".format(m.group(3),desc)
        else:
            citationpage = "kuva {}".format(m.group(3))
        url = m.group(5)
        date = m.group(6)
        details = "SSHY: {} / Viitattu {}".format(url,date)
        return Match(line,reponame,sourcetitle,citationpage,details,url,date)


    def match_svar(self,line):
    # Hajoms kyrkoarkiv, Husförhörslängder, SE/GLA/13195/A I/12 (1861-1872), bildid: C0045710_00045
        if line.find("bildid:") < 0: return None
        i = line.find("bildid:")
        bildid = line[i:].split()[1]
        line = line.replace("bildid:","SVAR bildid:")
        parts = line.split(",")
        reponame = parts[0]
        sourcetitle = ",".join(parts[0:3])
        citationpage = parts[3].strip()
        # https://sok.riksarkivet.se/bildvisning/C0060358_00162
        url = "https://sok.riksarkivet.se/bildvisning/" + bildid
        date = time.strftime("%d.%m.%Y",time.localtime(time.time()))
        details = "SVAR: {} / Viitattu {}".format(url,date)
        return Match(line,reponame,sourcetitle,citationpage,details,url,date)

#Vasabladet, 18.11.1911, nro 138, s. 4
#https://digi.kansalliskirjasto.fi/sanomalehti/binding/1340877?page=4
#Kansalliskirjaston Digitoidut aineistot
    def match_kansalliskirjasto(self,lines):
        self.log(repr(lines))
        if len(lines) < 3 or lines[2] != "Kansalliskirjaston Digitoidut aineistot": return None
        i = lines[0].find(",")
        if i < 0: return None
        sourcetitle = lines[0][:i].strip()
        citationpage = lines[0][i+1:].strip()
        reponame = lines[2]
        url = lines[1]
        date = time.strftime("%d.%m.%Y",time.localtime(time.time()))
        details = "Kansalliskirjasto: {} / Viitattu {}".format(url,date)
        return Match(lines,reponame,sourcetitle,citationpage,details,url,date)
        
    def yield_objects(self,step):
        for classname,funcs in self.primary_objects.items():
            for obj in funcs['iter_func']():
                step()
                obj.primary_object_class = classname
                obj.primary_object = obj
                yield classname,obj
                if hasattr(obj,'get_note_child_list'):
                    for obj2 in obj.get_note_child_list():
                        obj2.primary_object_class = classname
                        obj2.primary_object = obj
                        yield obj2.__class__.__name__, obj2

    def find_matching_notes(self,obj):
        if not isinstance(obj,NoteBase): return None
        if not isinstance(obj,CitationBase): return None
        for type,notehandle in obj.get_referenced_note_handles(): # type = 'Note'
            note = self.db.get_note_from_handle(notehandle)
            self.total_notes += 1
            m = self.match(note)
            if m:
                #pprint.pprint(m.__dict__)
                yield (note,m,notehandle)

    def get_repos(self):
        repos = defaultdict(Repository)
        for handle in self.db.iter_repository_handles():
            repo = self.db.get_repository_from_handle(handle)
            repo.in_db = True
            repos[repo.name] = repo
        return repos

    def get_sources(self):
        sources = defaultdict(Source)
        for handle in self.db.iter_source_handles():
            source = self.db.get_source_from_handle(handle)
            source.in_db = True
            sources[source.title] = source
        return sources
                                
    def run(self):
        objects = []
        skipped = 0
        total_objects = 0
        total_notes = 0
        matching_notes = 0
        citations_added = 0
        sources_added = 0
        repos_added = 0
        with self.user.progress(
                _("Generating citations"), '',
                self.db.get_total()) as step:

            repos = self.get_repos()
            sources = self.get_sources()
            notes_to_remove = {}
            for classname,obj in self.yield_objects(step):
                total_objects += 1
                obj.classname = classname
                obj.notes = []
                obj.citations = []
                current_citations = None
                for note,m,notehandle in self.find_matching_notes(obj):
                    matching_notes += 1
                        
                    # get a list of current citations; this is in the loop to avoid computing the set for all objects
                    if current_citations is None:
                        current_citations = set()
                        for type,h in obj.get_referenced_citation_handles(): # type = 'Citation'
                            citation = self.db.get_citation_from_handle(h)
                            page = citation.get_page()
                            current_citations.add(page)
                        
                    if m.citationpage in current_citations: 
                        skipped += 1
                        continue # already has this citation, skip
                    repo = repos[m.reponame]
                    repo.set_name(m.reponame)

                    source = sources[m.sourcetitle]
                    source.set_title(m.sourcetitle)
                    source.repo = repo

                    citation = Citation()
                    citation.set_page(m.citationpage)
                    citation.source = source
                    citation.note = m.details

                    obj.citations.append(citation)
                    obj.notes.append(notehandle)
                    
                    notelines = note.get().splitlines()
                    if len(notelines) == 1:
                        notes_to_remove[notehandle] = m
                if obj.notes: objects.append(obj)

            with DbTxn(_("Add citations"), self.db) as trans:
                for obj in objects:
                    self.log("Object {}".format(obj))
                    for citation in obj.citations:
                        source = citation.source
                        repo = source.repo
                        
                        citation_handle = self.db.add_citation(citation, trans)
                        source_handle = self.db.add_source(source, trans)
                        repo_handle = self.db.add_repository(repo, trans)

                        self.log("- Adding citation: {}".format(citation.get_page()))

                        if not hasattr(repo,"in_db"): 
                            repos_added += 1
                            self.log("- Adding repo: {}".format(repo.get_name()))
                            repo.in_db = True
                        if not hasattr(source,"in_db"): 
                            sources_added += 1
                            self.log("- Adding source: {}".format(source.get_title()))
                            source.in_db = True


                        note = Note()
                        note.set(citation.note)
                        note.set_type(NoteType.LINK)
                        note_handle = self.db.add_note(note, trans)
                        citation.add_note(note_handle)
                        citation.newnote = note
                        
                        citation.set_reference_handle(source_handle)
                        if not source.has_repo_reference(repo_handle):
                            reporef = RepoRef()
                            reporef.set_reference_handle(repo_handle)
                            source.add_repo_reference(reporef)
                        obj.add_citation(citation_handle)
                        citations_added += 1

                    for notehandle in obj.notes:
                        if notehandle in notes_to_remove:
                            obj.remove_note(notehandle)
                    
                    commit_func = self.primary_objects[obj.primary_object_class]['commit_func']
                    commit_func(obj.primary_object, trans)
                    for citation in obj.citations:
                        self.db.commit_citation(citation, trans)
                        self.db.commit_source(citation.source, trans)
                        self.db.commit_repository(source.repo, trans)
                        self.db.commit_note(citation.newnote, trans)

                for notehandle,m in notes_to_remove.items():
                    self.log("Removing note: {} {}".format(repr(notehandle),m.line))
                    self.db.remove_note(notehandle, trans)

            log = []
            log.append(_("Total objects processed: {total_objects}").format(total_objects=total_objects))
            log.append("- " + _("Total notes: {total_notes}").format(total_notes=self.total_notes))
            log.append("- " + _("Matching notes: {matching_notes}").format(matching_notes=matching_notes))
            log.append("- " + _("Unique matching notes: {unique_matching_notes}").format(unique_matching_notes=len(notes_to_remove)))
            log.append("- " + _("Skipped notes: {skipped}").format(skipped=skipped))
            log.append("- " + _("Citations added: {citations_added}").format(citations_added=citations_added))
            log.append("- " + _("Sources added: {sources_added}").format(sources_added=sources_added))
            log.append("- " + _("Repositories added: {repos_added}").format(repos_added=repos_added))
            msg = "\n".join(log)
            self.log(msg)
            OkDialog(_("All events processed"),
                     msg,
                     parent=self.uistate.window)




#------------------------------------------------------------------------
#
# GenerateCitationsOptions
#
#------------------------------------------------------------------------
class GenerateCitationsOptions(tool.ToolOptions):
    """
    Define options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

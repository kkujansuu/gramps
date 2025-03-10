# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
# Copyright (C) 2011 Tim G L Lyons
# Copyright (C) 2020 Matthias Kemmer
# Copyright (C) 2024 Kari Kujansuu
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

# ------------------------------------------------------------------------
#
# Gtk
#
# ------------------------------------------------------------------------
from gi.repository import Gtk

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.plug import Gramplet
from gramps.gui.editors import EditNote
from gramps.gui.widgets.styledtexteditor import StyledTextEditor
from gramps.gui.widgets import SimpleButton
from gramps.gen.lib import StyledText, Note
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext


class Notes(Gramplet):
    """
    Displays the notes for an object.
    """

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box()
        self.left = SimpleButton("go-previous", self.left_clicked)
        self.left.set_sensitive(False)
        hbox.pack_start(self.left, False, False, 0)
        self.right = SimpleButton("go-next", self.right_clicked)
        self.right.set_sensitive(False)
        hbox.pack_start(self.right, False, False, 0)
        self.page = Gtk.Label()
        self.page.set_halign(Gtk.Align.START)
        hbox.pack_start(self.page, True, True, 10)
        self.ntype = Gtk.Label()
        hbox.pack_start(self.ntype, False, False, 10)

        self.edit = Gtk.Button(_("Edit"))
        hbox.pack_start(self.edit, False, False, 0)
        self.edit.connect("clicked", self.edit_clicked)

        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.texteditor = StyledTextEditor()
        #self.texteditor = Gtk.TextView()
        self.texteditor.set_editable(False)
        self.texteditor.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolledwindow.add(self.texteditor)

        top.pack_start(hbox, False, False, 0)
        top.pack_start(scrolledwindow, True, True, 0)
        top.show_all()
        return top

    def get_notes(self, obj):
        """
        Get the note list for the current object.
        """
        self.left.set_sensitive(False)
        self.right.set_sensitive(False)
        self.texteditor.set_text(StyledText())
        #self.texteditor.get_buffer().set_text("")
        self.note_list = obj.get_note_list()
        self.page.set_text("")
        self.ntype.set_text("")
        if len(self.note_list) > 0:
            self.set_has_data(True)
            if len(self.note_list) > 1:
                self.right.set_sensitive(True)
            self.current = 0
            self.display_note()
        else:
            self.set_has_data(False)

    def clear_text(self):
        self.left.set_sensitive(False)
        self.right.set_sensitive(False)
        self.texteditor.set_text(StyledText())
        #self.texteditor.get_buffer().set_text("")
        self.page.set_text("")
        self.current = 0

    def display_note(self):
        """
        Display the current note.
        """
        note_handle = self.note_list[self.current]
        note = self.dbstate.db.get_note_from_handle(note_handle)
        with self.texteditor.undo_disabled():
            self.texteditor.set_text(note.get_styledtext())
            #self.texteditor.get_buffer().set_text(note.get())
            self.ntype.set_text(str(note.get_type()))
            self.page.set_text(
                _("%(current)d of %(total)d")
                % {"current": self.current + 1, "total": len(self.note_list)}
            )

    def left_clicked(self, button):
        """
        Display the previous note.
        """
        if self.current > 0:
            self.current -= 1
            self.right.set_sensitive(True)
            if self.current == 0:
                self.left.set_sensitive(False)
            self.display_note()

    def right_clicked(self, button):
        """
        Display the next note.
        """
        if self.current < len(self.note_list) - 1:
            self.current += 1
            self.left.set_sensitive(True)
            if self.current == len(self.note_list) - 1:
                self.right.set_sensitive(False)
            self.display_note()

    def get_has_data(self, obj):
        """
        Return True if the gramplet has data, else return False.
        """
        if obj is None:
            return False
        if obj.get_note_list():
            return True
        return False

    def edit_clicked(self, button):
        """
        Display the note editor
        """
        if len(self.note_list) > 0:
            note_handle = self.note_list[self.current]
            note = self.dbstate.db.get_note_from_handle(note_handle)
        else:
            note = Note()

        def callback(*args):
            if len(self.note_list) == 0:
                with DbTxn(_("Adding a note"), self.dbstate.db) as trans:
                    self.add_note(note, trans)
                    self.note_list.append(note.handle)
                self.set_has_data(True)
            self.display_note()

        try:
            EditNote(self.dbstate, self.uistate, [], note, callback)
        except gramps.gen.errors.WindowActiveError:
            pass
            
    def add_note(self, note, trans):
        clsname = self.__class__.__name__  # e.g. PersonNotes
        objtype = clsname.replace("Notes", "") # -> Person
        getfuncname = "get_{}_from_handle".format(objtype.lower())
        getfunc = getattr(self.dbstate.db, getfuncname)
        commitfuncname = "commit_{}".format(objtype.lower())
        commitfunc = getattr(self.dbstate.db, commitfuncname)
        active_handle = self.get_active(objtype)
        if active_handle:
            active_obj = getfunc(active_handle)
            active_obj.add_note(note.handle)
            commitfunc(active_obj, trans)

class PersonNotes(Notes):
    """
    Displays the notes for a person.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "person-update", self.update)

    def active_changed(self, handle):
        self.update()

    def update_has_data(self):
        active_handle = self.get_active("Person")
        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Person")
        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class EventNotes(Notes):
    """
    Displays the notes for an event.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "event-update", self.update)
        self.connect_signal("Event", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Event")
        if active_handle:
            active = self.dbstate.db.get_event_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Event")
        if active_handle:
            active = self.dbstate.db.get_event_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class FamilyNotes(Notes):
    """
    Displays the notes for a family.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "family-update", self.update)
        self.connect_signal("Family", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Family")
        if active_handle:
            active = self.dbstate.db.get_family_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Family")
        if active_handle:
            active = self.dbstate.db.get_family_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class PlaceNotes(Notes):
    """
    Displays the notes for a place.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "place-update", self.update)
        self.connect_signal("Place", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Place")
        if active_handle:
            active = self.dbstate.db.get_place_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Place")
        if active_handle:
            active = self.dbstate.db.get_place_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class SourceNotes(Notes):
    """
    Displays the notes for a source.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "source-update", self.update)
        self.connect_signal("Source", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Source")
        if active_handle:
            active = self.dbstate.db.get_source_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Source")
        if active_handle:
            active = self.dbstate.db.get_source_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class CitationNotes(Notes):
    """
    Displays the notes for a Citation.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "citation-update", self.update)
        self.connect_signal("Citation", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Citation")
        if active_handle:
            active = self.dbstate.db.get_citation_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Citation")
        if active_handle:
            active = self.dbstate.db.get_citation_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class RepositoryNotes(Notes):
    """
    Displays the notes for a repository.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "repository-update", self.update)
        self.connect_signal("Repository", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Repository")
        if active_handle:
            active = self.dbstate.db.get_repository_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Repository")
        if active_handle:
            active = self.dbstate.db.get_repository_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class MediaNotes(Notes):
    """
    Displays the notes for a media object.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "media-update", self.update)
        self.connect_signal("Media", self.update)

    def update_has_data(self):
        active_handle = self.get_active("Media")
        if active_handle:
            active = self.dbstate.db.get_media_from_handle(active_handle)
            self.set_has_data(self.get_has_data(active))
        else:
            self.set_has_data(False)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Media")
        if active_handle:
            active = self.dbstate.db.get_media_from_handle(active_handle)
            if active:
                self.get_notes(active)
            else:
                self.set_has_data(False)
        else:
            self.set_has_data(False)


class NoteNotes(Notes):
    """
    Display a single note in NoteView.
    """

    def db_changed(self):
        self.connect(self.dbstate.db, "note-update", self.update)
        self.connect_signal("Note", self.update)

    def main(self):
        self.clear_text()
        active_handle = self.get_active("Note")
        if active_handle:
            active = self.dbstate.db.get_note_from_handle(active_handle)
            if active:
                self.texteditor.set_text(active.get_styledtext())


#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Kari Kujansuu
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
# Python modules
#
# ------------------------------------------------------------------------
import traceback

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

from gi.repository import Gtk

from gramps.gui import dialog
from gramps.gui.dialog  import ErrorDialog

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Original ErrorDialog:
#
#    class ErrorDialog(Gtk.MessageDialog):
#        def __init__(self, msg1, msg2="", parent=None):
#            Gtk.MessageDialog.__init__(
#                self, transient_for=parent, modal=True, message_type=Gtk.MessageType.ERROR
#            )
#            self.add_button(_("_Close"), Gtk.ResponseType.CLOSE)
#            self.set_markup('<span weight="bold" size="larger">%s</span>' % str(msg1))
#            self.format_secondary_text(msg2)
#            self.set_icon(ICON)
#            self.set_title("%s - Gramps" % str(msg1))
#            if parent:
#                parent_modal = parent.get_modal()
#                if parent_modal:
#                    parent.set_modal(False)
#            self.show()
#            self.run()
#            self.destroy()
#            if parent and parent_modal:
#                parent.set_modal(True)
#
#


def load_on_reg(dbstate, uistate, plugin):
    # patch the ErrorDialog class
    ErrorDialog.run = run_dialog

def run_dialog(self):
    # This function replaces Gtk.MessageDialog.run() within the ErrorDialog.
    # The function adds the "Details" link and stack trace.

    def toggle_details(*args):
        if textview.is_visible():
            textview.hide()
        else:
            textview.show()

    content = self.get_content_area()

    link = Gtk.Label()
    link.set_markup('<a href="#">' + _('Details') + '</a>')
    link.connect("button_press_event", toggle_details)
    link.show()
    content.add(link)

    text = "".join(traceback.format_stack()[:-1])
    
    textview = Gtk.TextView()
    buffer = textview.get_buffer()
    buffer.set_text(text)
    content.add(textview)

    Gtk.MessageDialog.run(self)



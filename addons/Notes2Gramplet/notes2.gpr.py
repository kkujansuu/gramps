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

from gramps.version import major_version

namespaces = [
    "Person",
    "Family",
    "Event",
    "Place",
    "Citation",
    "Source",
    "Repository",
    "Media",
#   "Note",
]

for namespace in namespaces:
    register(GRAMPLET,
             id=namespace + "Notes2",
             name=_(namespace + " Notes2"),
             description = _("Gramplet showing the notes for an object"),
             version="1.0.0",
             gramps_target_version=major_version,
             status = STABLE,
             fname="notes2.py",
             height=200,
             gramplet = namespace + 'Notes',
             gramplet_title=_("Notes2"),
             navtypes=[namespace],
             )

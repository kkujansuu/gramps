#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      KKu
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


"""
Gramps registration file
"""
from gramps.version import major_version
from gramps.gui import plug

CATEGORY = "Experimental tools"
plug.tool.tool_categories[CATEGORY] = ("Experimental", _(CATEGORY))

# ------------------------------------------------------------------------
#
# Fulltext
#
# ------------------------------------------------------------------------

register(TOOL,
    id="Fulltext",
    name=_("Fulltext Search"),
    description=_("Fulltext Search"),
    version="0.9.3",
    gramps_target_version=major_version,
    status=STABLE,
    fname="fulltext.py",
    authors=["KKu"],
    category=CATEGORY,
    toolclass="Tool",
    optionclass="Options",
    tool_modes=[TOOL_MODE_GUI],
)


register(GENERAL,
    id="whoosh",
    name=_("whoosh library loader"),
    description=_("whoosh full text search library"),
    version="0.9.3",
    gramps_target_version=major_version,
    status=STABLE,
    fname="fulltext_loader.py",
    load_on_reg=True,
)

#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021      KKu
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
from gramps.gui import plug
from gramps.version import major_version

plug.tool.tool_categories["Isotammi"] = ("Isotammi", _("Isotammi tools"))

#------------------------------------------------------------------------
#
# FilterParams
#
#------------------------------------------------------------------------

register(
    TOOL,
    id="FilterParams",
    name=_("FilterParams"),
    description=_("Display custom filters and allow changing their parameters"),
    version="1.0.1",
    gramps_target_version=major_version,
    status=STABLE,
    fname="FilterParams.py",
    authors=["Kari Kujansuu"],
    category="Isotammi",
    toolclass="Tool",
    optionclass="Options",
    tool_modes=[TOOL_MODE_GUI],
)

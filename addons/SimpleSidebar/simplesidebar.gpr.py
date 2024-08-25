#
# Gramps - a GTK+/GNOME based genealogy program
#
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
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.version import major_version, VERSION_TUPLE

_ = glocale.translation.gettext

register(
    SIDEBAR,
    id="simplesidebar",
    name=_("Simple Sidebar"),
    description=_("Selection of views from a simple list"),
    version="1.0",
    gramps_target_version=major_version,
    status=STABLE,
    fname="simplesidebar.py",
    authors=["Kari Kujansuu"],
    authors_email=["kari.kujansuu@gmail.com"],
    sidebarclass="SimpleSidebar",
    menu_label=_("Simple"),
    order=END,
)

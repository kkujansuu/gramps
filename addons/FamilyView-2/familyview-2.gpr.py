# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
# Copyright (C) 2009 Douglas S. Blank
# Copyright (C) 2009 Nick Hall
# Copyright (C) 2011 Tim G L Lyons
# Copyright (C) 2025 Kari Kujansuu
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

_ = glocale.translation.gettext

from gramps.version import major_version, VERSION_TUPLE

# ------------------------------------------------------------------------
#
# default views of Gramps
#
# ------------------------------------------------------------------------


register(
    VIEW,
    id="familyview-2",
    name=_("FamilyView-2"),
    description=_("FamilyView with additional columns"),
    version="0.9.0",
    gramps_target_version=major_version,
    status=STABLE,
    fname="familyview-2.py",
    authors=["The Gramps project", "Kari Kujansuu"],
    authors_email=["http://gramps-project.org", "kari.kujansuu@gmail.com"],
    category=("Families", _("Families")),
    viewclass="FamilyView",
    order=END,
    stock_icon="geo-show-family",
)




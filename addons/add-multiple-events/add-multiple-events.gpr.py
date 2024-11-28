#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2023 Kari Kujansuu
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
from gramps.gen.plug._pluginreg import *
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

from gramps.version import major_version

#------------------------------------------------------------------------
#
# add-multiple-events
#
#------------------------------------------------------------------------

register(QUICKREPORT,
    id = 'add-multiple-events-family',
    name = _("Add events to Family members"),
    description = _("Add or share events to members of a Family"),
    version = '1.2',
    gramps_target_version = major_version,
    status = STABLE,
    fname = 'add-multiple-events.py',
    authors = ["Kari Kujansuu"],
    category = CATEGORY_QR_FAMILY,
    runfunc = 'run'
)

register(QUICKREPORT,
    id = 'add-multiple-events-person',
    name = _("Add events to extended Family"),
    description = _("Add or share events to a Person and their spouses, children, parents"),
    version = '1.2',
    gramps_target_version = major_version,
    status = STABLE,
    fname = 'add-multiple-events.py',
    authors = ["Kari Kujansuu"],
    category = CATEGORY_QR_PERSON,
    runfunc = 'run'
)


#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024      Kari Kujansuu
# Copyright (C) 2026      Claude AI (wish coding by Brian McCullough)
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
Registration only. The code that adds a Cancel button to the filter
progress window lives in filterprogress.py.

load_on_reg=True makes Gramps import filterprogress.py once at startup
and call its load_on_reg() function, which installs the replacement
methods on GenericFilter. Because this is now an ordinary registered
plugin, deactivating "Filter Progress" in the Plugin Manager stops the
patch from being installed at the next start.
"""

from gramps.version import major_version, VERSION_TUPLE

if (5, 2, 0) <= VERSION_TUPLE <= (6, 2, 0):
    register(
        GENERAL,
        id="FilterProgress",
        name=_("Filter Progress"),
        description=_(
            "Adds a Cancel button to the progress window shown while a " "filter runs"
        ),
        version="2.0.0",  # build 20261021.1634
        gramps_target_version=major_version,
        status=STABLE,
        fname="filterprogress.py",
        load_on_reg=True,
        authors=["Kari Kujansuu"],
        authors_email=["kari.kujansuu@gmail.com"],
    )

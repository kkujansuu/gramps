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

from gramps.version import major_version

register(
    GENERAL,
    id="ErrorDetails",
    name=_("ErrorDetails"),
    description=_("Addon that adds details of the error (stack trace) to ErrorDialog"),
    version="0.9.0",
    authors=["Kari Kujansuu"],
    gramps_target_version=major_version,
    status=STABLE,
    fname="ErrorDetails.py",
    load_on_reg=True,
)



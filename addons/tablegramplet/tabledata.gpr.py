# tabledata.gpr.py
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C)  2026  Kari Kujansuu
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
tabledata.gpr.py  –  registration for all TableData gramplets.

Installation
------------
Copy the whole TableData/ folder into your Gramps user plugins directory:

  Linux / macOS : ~/.gramps/gramps<VER>/plugins/TableData/
  Windows       : %APPDATA%\gramps\gramps<VER>\plugins\TableData\

The folder must contain all tabledata_*.py files and this .gpr.py file.

Data storage
------------
All data is kept in  <family-tree-folder>/tabledata.db  (SQLite).
The column schema is shared across all objects of the same type.
Each object stores its own independent set of rows, keyed by its Gramps handle.
"""

from gramps.version import major_version

register(
    GRAMPLET,
    id              = "TableDataPerson",
    name            = _("Person Table Data"),
    description     = _("Per-person arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Person objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_person.py",
    gramplet        = "TableDataPerson",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Person Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Person"],
)

register(
    GRAMPLET,
    id              = "TableDataFamily",
    name            = _("Family Table Data"),
    description     = _("Per-family arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Family objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_family.py",
    gramplet        = "TableDataFamily",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Family Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Family"],
)

register(
    GRAMPLET,
    id              = "TableDataEvent",
    name            = _("Event Table Data"),
    description     = _("Per-event arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Event objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_event.py",
    gramplet        = "TableDataEvent",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Event Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Event"],
)

register(
    GRAMPLET,
    id              = "TableDataPlace",
    name            = _("Place Table Data"),
    description     = _("Per-place arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Place objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_place.py",
    gramplet        = "TableDataPlace",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Place Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Place"],
)

register(
    GRAMPLET,
    id              = "TableDataSource",
    name            = _("Source Table Data"),
    description     = _("Per-source arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Source objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_source.py",
    gramplet        = "TableDataSource",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Source Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Source"],
)

register(
    GRAMPLET,
    id              = "TableDataCitation",
    name            = _("Citation Table Data"),
    description     = _("Per-citation arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Citation objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_citation.py",
    gramplet        = "TableDataCitation",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Citation Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Citation"],
)

register(
    GRAMPLET,
    id              = "TableDataRepository",
    name            = _("Repository Table Data"),
    description     = _("Per-repository arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Repository objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_repository.py",
    gramplet        = "TableDataRepository",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Repository Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Repository"],
)

register(
    GRAMPLET,
    id              = "TableDataMedia",
    name            = _("Media Table Data"),
    description     = _("Per-media-object arbitrary typed tabular data. Columns (Number / String / URL) are shared "
                        "across all Media objects; rows are stored per "
                        "object. Click a column header to sort."),
    version         = "1.0.0",
    gramps_target_version = major_version,
    status          = STABLE,
    fname           = "tabledata_media.py",
    gramplet        = "TableDataMedia",
    height          = 300,
    expand          = True,
    gramplet_title  = _("Media Table Data"),
    detached_width  = 700,
    detached_height = 400,
    navtypes        = ["Media"],
)

# ---------------------------------------------------------------------------
# Filter rules — one per object type
# ---------------------------------------------------------------------------
# Parameters presented to the user in the filter editor:
#   [0] Table name       – name of the TableData table to search
#   [1] Column name      – column to search (leave empty to search all columns)
#   [2] Value            – value to find   (leave empty to match any value)
#   [3] Match type       – contains | equals | starts with | ends with
#   [4] Negate           – if checked, match objects that do NOT satisfy the rule

register(
    RULE,
    id          = "TableDataRulePerson",
    name        = _("Person has TableData value"),
    description = _("Matches people whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRulePerson",
    namespace   = "Person",
)

register(
    RULE,
    id          = "TableDataRuleFamily",
    name        = _("Family has TableData value"),
    description = _("Matches families whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleFamily",
    namespace   = "Family",
)

register(
    RULE,
    id          = "TableDataRuleEvent",
    name        = _("Event has TableData value"),
    description = _("Matches events whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleEvent",
    namespace   = "Event",
)

register(
    RULE,
    id          = "TableDataRulePlace",
    name        = _("Place has TableData value"),
    description = _("Matches places whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRulePlace",
    namespace   = "Place",
)

register(
    RULE,
    id          = "TableDataRuleSource",
    name        = _("Source has TableData value"),
    description = _("Matches sources whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleSource",
    namespace   = "Source",
)

register(
    RULE,
    id          = "TableDataRuleCitation",
    name        = _("Citation has TableData value"),
    description = _("Matches citations whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleCitation",
    namespace   = "Citation",
)

register(
    RULE,
    id          = "TableDataRuleRepository",
    name        = _("Repository has TableData value"),
    description = _("Matches repositories whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleRepository",
    namespace   = "Repository",
)

register(
    RULE,
    id          = "TableDataRuleMedia",
    name        = _("Media object has TableData value"),
    description = _("Matches media objects whose TableData rows contain a specified value"),
    version     = "1.0.0",
    gramps_target_version = major_version,
    status      = STABLE,
    fname       = "tabledata_rule.py",
    ruleclass   = "TableDataRuleMedia",
    namespace   = "Media",
)

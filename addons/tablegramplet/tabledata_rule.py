# tabledata_rule.py
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024  (your name)
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

"""
tabledata_rule.py  –  Gramps filter rules for the TableData addon.

One rule class is defined per primary object type (Person, Family, …).
Each rule appears in the "TableData filters" category in the filter editor
and lets the user match objects by the values stored in their TableData rows.

Rule parameters
---------------
  Table name  : name of the TableData table to search (case-insensitive)
  Column name : name of the column to match (case-insensitive; empty = any)
  Value       : substring to look for (case-insensitive; empty = any value)
  Match type  : "contains" | "equals" | "starts with" | "ends with"
  Negate      : if checked, return objects that do NOT match

How it works
------------
prepare() opens the tabledata.db for the current tree, resolves the table_id
and col_order from the user-supplied names, and builds the matching set of
handles once.  apply() is then a simple set lookup, making repeated calls
(once per object) very cheap.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Optional

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters.rules import Rule

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
 

# ---------------------------------------------------------------------------
# Match-type constants (stored as the list index in self.list[3])
# ---------------------------------------------------------------------------
MATCH_CONTAINS    = "contains"
MATCH_EQUALS      = "equals"
MATCH_STARTS_WITH = "starts with"
MATCH_ENDS_WITH   = "ends with"
MATCH_TYPES       = [MATCH_CONTAINS, MATCH_EQUALS, MATCH_STARTS_WITH, MATCH_ENDS_WITH]


# ---------------------------------------------------------------------------
# Helper: open tabledata.db read-only for the current tree
# ---------------------------------------------------------------------------
def _open_db(db: Any) -> Optional[sqlite3.Connection]:
    """Return a read-only sqlite3 connection to tabledata.db, or None."""
    try:
        path = os.path.join(db.get_save_path(), "tabledata.db")
        if not os.path.exists(path):
            return None
        # uri=True + ?mode=ro opens read-only without creating the file
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                              check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        return None


def _match_value(cell: str, pattern: str, match_type: str) -> bool:
    """Return True if *cell* matches *pattern* according to *match_type*."""
    cell    = cell.lower()
    pattern = pattern.lower()
    if match_type == MATCH_EQUALS:
        return cell == pattern
    if match_type == MATCH_STARTS_WITH:
        return cell.startswith(pattern)
    if match_type == MATCH_ENDS_WITH:
        return cell.endswith(pattern)
    # default: contains
    return pattern in cell


# ---------------------------------------------------------------------------
# Base rule
# ---------------------------------------------------------------------------
class TableDataRuleBase(Rule):
    """
    Base class for all TableData filter rules.

    Subclasses must set:
        object_type : str   e.g. "Person"

    self.list holds the four parameter values in order:
        [0] table_name   – name of the TableData table (case-insensitive)
        [1] column_name  – column to search (empty → search all columns)
        [2] value        – substring to find (empty → match any value)
        [3] match_type   – one of MATCH_TYPES (default "contains")
        [4] negate       – "1" if the result should be inverted, else "0"
    """

    object_type: str = "Unknown"

    labels = [
        _("Table name:"),
        _("Column name (empty = any):"),
        _("Value (empty = any):"),
        _("Match type:"),
        _("Negate (find objects that do NOT match):"),
    ]

    # Shown in the filter editor rule picker
    name        = _("Has TableData value")
    description = _("Matches objects whose TableData rows contain a specified value")
    category    = _("TableData filters")

    def prepare(self, db: Any, user: Any) -> None:
        """
        Build the set of matching handles once before apply() is called
        repeatedly.  Opening the DB and running the query here keeps
        apply() to an O(1) set lookup.
        """
        self._matching_handles: set[str] = set()

        table_name  = (self.list[0] if len(self.list) > 0 else "").strip()
        column_name = (self.list[1] if len(self.list) > 1 else "").strip()
        value       = (self.list[2] if len(self.list) > 2 else "").strip()
        match_type  = (self.list[3] if len(self.list) > 3 else MATCH_CONTAINS).strip()
        negate      = (self.list[4] if len(self.list) > 4 else "0").strip() == "1"

        if match_type not in MATCH_TYPES:
            match_type = MATCH_CONTAINS

        con = _open_db(db)
        if con is None:
            return

        try:
            self._build_matching_set(
                con, db, table_name, column_name, value, match_type, negate)
        finally:
            con.close()

    def _build_matching_set(
            self,
            con: sqlite3.Connection,
            db: Any,
            table_name: str,
            column_name: str,
            value: str,
            match_type: str,
            negate: bool) -> None:

        # ── resolve table_id ───────────────────────────────────────────────
        if not table_name:
            # No table specified: match all tables for this object type
            cur = con.execute(
                "SELECT id FROM tables WHERE object_type=?",
                (self.object_type,))
            table_ids = [r["id"] for r in cur]
        else:
            cur = con.execute(
                "SELECT id FROM tables "
                "WHERE object_type=? AND LOWER(name)=LOWER(?)",
                (self.object_type, table_name))
            row = cur.fetchone()
            if row is None:
                return   # table not found → no matches
            table_ids = [row["id"]]

        if not table_ids:
            return

        # ── resolve col_order ──────────────────────────────────────────────
        col_orders: Optional[list[int]] = None   # None = all columns
        if column_name:
            col_orders = []
            for tid in table_ids:
                cur = con.execute(
                    "SELECT col_order FROM columns "
                    "WHERE table_id=? AND LOWER(name)=LOWER(?)",
                    (tid, column_name))
                for r in cur:
                    col_orders.append(r["col_order"])
            if not col_orders:
                return   # column not found → no matches

        # ── fetch candidate rows ───────────────────────────────────────────
        # Build the SQL to retrieve distinct handles and their cell values.
        ph_tables = ",".join("?" * len(table_ids))
        base_sql = (
            f"SELECT DISTINCT object_handle, value FROM rows "
            f"WHERE table_id IN ({ph_tables})"
        )
        params: list[Any] = list(table_ids)

        if col_orders is not None:
            ph_cols = ",".join("?" * len(col_orders))
            base_sql += f" AND col_order IN ({ph_cols})"
            params.extend(col_orders)

        cur = con.execute(base_sql, params)

        # ── match ──────────────────────────────────────────────────────────
        if not value:
            # No value filter: every handle that has any row in the table
            candidates: set[str] = {r["object_handle"] for r in cur}
        else:
            candidates = set()
            for r in cur:
                if _match_value(r["value"], value, match_type):
                    candidates.add(r["object_handle"])

        # ── negate ─────────────────────────────────────────────────────────
        if negate:
            # All handles of this type that are NOT in candidates
            all_handles = self._all_handles(db)
            self._matching_handles = all_handles - candidates
        else:
            self._matching_handles = candidates

    def _all_handles(self, db: Any) -> set[str]:
        """Return the set of all handles for self.object_type."""
        _ITER_FN = {
            "Person":     "iter_person_handles",
            "Family":     "iter_family_handles",
            "Event":      "iter_event_handles",
            "Place":      "iter_place_handles",
            "Source":     "iter_source_handles",
            "Citation":   "iter_citation_handles",
            "Repository": "iter_repository_handles",
            "Media":      "iter_media_handles",
        }
        fn = getattr(db, _ITER_FN.get(self.object_type, ""), None)
        if fn is None:
            return set()
        return set(fn())

    def apply(self, db: Any, obj: Any) -> bool:
        """Return True if *obj* is in the pre-built matching set."""
        return obj.get_handle() in self._matching_handles


# ---------------------------------------------------------------------------
# One concrete rule class per object type
# (Gramps requires a distinct class per namespace)
# ---------------------------------------------------------------------------

class TableDataRulePerson(TableDataRuleBase):
    object_type = "Person"
    name        = _("Person has TableData value")
    description = _("Matches people whose TableData rows contain a specified value")


class TableDataRuleFamily(TableDataRuleBase):
    object_type = "Family"
    name        = _("Family has TableData value")
    description = _("Matches families whose TableData rows contain a specified value")


class TableDataRuleEvent(TableDataRuleBase):
    object_type = "Event"
    name        = _("Event has TableData value")
    description = _("Matches events whose TableData rows contain a specified value")


class TableDataRulePlace(TableDataRuleBase):
    object_type = "Place"
    name        = _("Place has TableData value")
    description = _("Matches places whose TableData rows contain a specified value")


class TableDataRuleSource(TableDataRuleBase):
    object_type = "Source"
    name        = _("Source has TableData value")
    description = _("Matches sources whose TableData rows contain a specified value")


class TableDataRuleCitation(TableDataRuleBase):
    object_type = "Citation"
    name        = _("Citation has TableData value")
    description = _("Matches citations whose TableData rows contain a specified value")


class TableDataRuleRepository(TableDataRuleBase):
    object_type = "Repository"
    name        = _("Repository has TableData value")
    description = _("Matches repositories whose TableData rows contain a specified value")


class TableDataRuleMedia(TableDataRuleBase):
    object_type = "Media"
    name        = _("Media object has TableData value")
    description = _("Matches media objects whose TableData rows contain a specified value")

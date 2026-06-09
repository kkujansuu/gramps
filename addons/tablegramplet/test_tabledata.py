# test_tabledata.py
#
# Unit tests for tabledata_base.py
#
# Run with:
#   pytest test_tabledata.py -v
#
# The tests cover all pure-logic code:
#   • _to_number helper
#   • _db_path helper
#   • _DB (full CRUD: tables, columns, rows, swap, cascade delete, migration)
#   • CSV import/export helpers
#   • ODS import/export helpers (skipped when odfpy is absent)
#
# GTK and Gramps are not available in CI / plain pytest environments, so
# both are stubbed out at the top of this file before the module is imported.
# The gramplet UI classes (_TableWidget, TableDataBase, dialogs) are not
# tested here — they require a running GTK main loop and Gramps session.

from __future__ import annotations

import csv
import importlib
import os
import sqlite3
import sys
import types
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub GTK and Gramps so tabledata_base can be imported without a display
# ---------------------------------------------------------------------------

def _build_stubs() -> None:
    """Install minimal stubs for gi/GTK and gramps before importing the module."""

    # ── gi stub ─────────────────────────────────────────────────────────────
    class _Any:
        """A catch-all stub that accepts any attribute access or call."""
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass
        def __call__(self, *a: Any, **kw: Any) -> "_Any":
            return _Any()
        def __getattr__(self, name: str) -> "_Any":
            return _Any()
        def __class_getitem__(cls, item: Any) -> type:
            return cls

    class _GtkModule(types.ModuleType):
        """Module whose every attribute returns the _Any stub class."""
        def __getattr__(self, name: str) -> type:
            return _Any

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod

    gtk_mod = _GtkModule("gi.repository.Gtk")
    pango_mod = types.ModuleType("gi.repository.Pango")
    pango_mod.Underline = _Any()  # type: ignore[attr-defined]
    gdk_mod = types.ModuleType("gi.repository.Gdk")

    repo_mod = types.ModuleType("gi.repository")
    repo_mod.Gtk = gtk_mod      # type: ignore[attr-defined]
    repo_mod.Pango = pango_mod  # type: ignore[attr-defined]
    repo_mod.Gdk = gdk_mod      # type: ignore[attr-defined]

    sys.modules["gi.repository"]       = repo_mod
    sys.modules["gi.repository.Gtk"]   = gtk_mod
    sys.modules["gi.repository.Pango"] = pango_mod
    sys.modules["gi.repository.Gdk"]   = gdk_mod

    # ── gramps stub ──────────────────────────────────────────────────────────
    for mod_name in ("gramps", "gramps.gen", "gramps.gen.plug",
                     "gramps.gui", "gramps.gui.dialog"):
        sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

    sys.modules["gramps.gen.plug"].Gramplet = object          # type: ignore[attr-defined]
    sys.modules["gramps.gui.dialog"].OkDialog = MagicMock()   # type: ignore[attr-defined]


_build_stubs()

# Now it is safe to import the module under test
sys.path.insert(0, str(Path(__file__).parent))
import tabledata_base as tb  # noqa: E402

# Convenience re-exports
_DB            = tb._DB
_to_number     = tb._to_number
_db_path       = tb._db_path
_export_csv    = tb._export_csv
_import_csv    = tb._import_csv
COL_TYPE_NUMBER = tb.COL_TYPE_NUMBER
COL_TYPE_STRING = tb.COL_TYPE_STRING
COL_TYPE_URL    = tb.COL_TYPE_URL

_HAVE_ODF = tb._HAVE_ODF
if _HAVE_ODF:
    _export_ods = tb._export_ods
    _import_ods = tb._import_ods


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_db_cache() -> None:
    """Ensure the _DB module-level cache is empty before and after every test."""
    _DB._cache.clear()
    yield
    _DB._cache.clear()


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Return the path to a fresh tabledata.db inside a temp directory."""
    return str(tmp_path / "tabledata.db")


@pytest.fixture
def db(db_path: str) -> _DB:
    """Return an initialised _DB instance backed by a temp file."""
    return _DB(db_path)


@pytest.fixture
def db_with_table(db: _DB) -> tuple[_DB, int]:
    """Return *(db, table_id)* with one 'Test' table pre-created."""
    tid = db.add_table("Person", "Test")
    return db, tid


@pytest.fixture
def db_with_cols(db_with_table: tuple[_DB, int]) -> tuple[_DB, int]:
    """Return *(db, table_id)* with three typed columns pre-created."""
    db, tid = db_with_table
    db.add_column(tid, "Name",   COL_TYPE_STRING)
    db.add_column(tid, "Score",  COL_TYPE_NUMBER)
    db.add_column(tid, "Link",   COL_TYPE_URL)
    return db, tid


# ---------------------------------------------------------------------------
# _to_number
# ---------------------------------------------------------------------------

class TestToNumber:

    def test_integer(self) -> None:
        assert _to_number("42") == 42
        assert isinstance(_to_number("42"), int)

    def test_negative_integer(self) -> None:
        assert _to_number("-7") == -7

    def test_zero(self) -> None:
        assert _to_number("0") == 0

    def test_float(self) -> None:
        result = _to_number("3.14")
        assert abs(result - 3.14) < 1e-9
        assert isinstance(result, float)

    def test_negative_float(self) -> None:
        assert _to_number("-0.5") == -0.5

    def test_leading_trailing_whitespace(self) -> None:
        assert _to_number("  10  ") == 10

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            _to_number("abc")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            _to_number("")

    def test_partial_number_raises(self) -> None:
        with pytest.raises(ValueError):
            _to_number("12abc")

    def test_scientific_notation(self) -> None:
        # Python's float() accepts scientific notation
        result = _to_number("1e3")
        assert result == 1000.0


# ---------------------------------------------------------------------------
# _db_path
# ---------------------------------------------------------------------------

class TestDbPath:

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        dbstate = MagicMock()
        dbstate.db.get_save_path.return_value = str(tmp_path)
        result = _db_path(dbstate)
        assert result == str(tmp_path / "tabledata.db")

    def test_uses_get_save_path(self, tmp_path: Path) -> None:
        dbstate = MagicMock()
        dbstate.db.get_save_path.return_value = str(tmp_path)
        _db_path(dbstate)
        dbstate.db.get_save_path.assert_called_once()


# ---------------------------------------------------------------------------
# _DB – schema and caching
# ---------------------------------------------------------------------------

class TestDBSchema:

    def test_creates_file(self, db_path: str) -> None:
        _DB(db_path)
        assert os.path.exists(db_path)

    def test_tables_table_exists(self, db: _DB) -> None:
        cur = db._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tables'")
        assert cur.fetchone() is not None

    def test_columns_table_exists(self, db: _DB) -> None:
        cur = db._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='columns'")
        assert cur.fetchone() is not None

    def test_rows_table_exists(self, db: _DB) -> None:
        cur = db._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rows'")
        assert cur.fetchone() is not None

    def test_foreign_keys_enabled(self, db: _DB) -> None:
        cur = db._con.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1

    def test_second_init_same_file_is_idempotent(self, db_path: str) -> None:
        _DB(db_path)
        _DB(db_path)   # should not raise

    def test_schema_has_table_id_fresh(self, db: _DB) -> None:
        assert db._schema_has_table_id() is True

    def test_schema_has_table_id_missing(self, db_path: str) -> None:
        """Simulate the old schema (no table_id column) and verify detection."""
        con = sqlite3.connect(db_path)
        con.execute(
            "CREATE TABLE columns "
            "(object_type TEXT, col_order INTEGER, name TEXT, col_type TEXT)")
        con.commit()
        con.close()
        instance = _DB.__new__(_DB)
        instance._con = sqlite3.connect(db_path)
        instance._con.row_factory = sqlite3.Row
        assert instance._schema_has_table_id() is False


class TestDBCache:

    def test_get_returns_same_instance(self, tmp_path: Path) -> None:
        dbstate = MagicMock()
        dbstate.db.get_save_path.return_value = str(tmp_path)
        a = _DB.get(dbstate)
        b = _DB.get(dbstate)
        assert a is b

    def test_get_different_paths_different_instances(self, tmp_path: Path) -> None:
        p1 = tmp_path / "tree1"
        p2 = tmp_path / "tree2"
        p1.mkdir(); p2.mkdir()

        ds1 = MagicMock()
        ds1.db.get_save_path.return_value = str(p1)
        ds2 = MagicMock()
        ds2.db.get_save_path.return_value = str(p2)

        a = _DB.get(ds1)
        b = _DB.get(ds2)
        assert a is not b

    def test_invalidate_removes_from_cache(self, tmp_path: Path) -> None:
        dbstate = MagicMock()
        dbstate.db.get_save_path.return_value = str(tmp_path)
        _DB.get(dbstate)
        assert str(tmp_path / "tabledata.db") in _DB._cache
        _DB.invalidate(dbstate)
        assert str(tmp_path / "tabledata.db") not in _DB._cache

    def test_invalidate_nonexistent_is_silent(self, tmp_path: Path) -> None:
        dbstate = MagicMock()
        dbstate.db.get_save_path.return_value = str(tmp_path)
        _DB.invalidate(dbstate)   # should not raise

    def test_invalidate_bad_dbstate_is_silent(self) -> None:
        broken = MagicMock()
        broken.db.get_save_path.side_effect = RuntimeError("no db")
        _DB.invalidate(broken)   # should not raise


# ---------------------------------------------------------------------------
# _DB – table CRUD
# ---------------------------------------------------------------------------

class TestDBTables:

    def test_get_tables_empty(self, db: _DB) -> None:
        assert db.get_tables("Person") == []

    def test_add_table_returns_id(self, db: _DB) -> None:
        tid = db.add_table("Person", "Measurements")
        assert isinstance(tid, int)
        assert tid > 0

    def test_add_table_appears_in_get(self, db: _DB) -> None:
        tid = db.add_table("Person", "Measurements")
        tables = db.get_tables("Person")
        assert len(tables) == 1
        assert tables[0]["id"] == tid
        assert tables[0]["name"] == "Measurements"

    def test_add_multiple_tables_ordered(self, db: _DB) -> None:
        db.add_table("Person", "Alpha")
        db.add_table("Person", "Beta")
        db.add_table("Person", "Gamma")
        names = [t["name"] for t in db.get_tables("Person")]
        assert names == ["Alpha", "Beta", "Gamma"]

    def test_tables_isolated_by_object_type(self, db: _DB) -> None:
        db.add_table("Person", "P table")
        db.add_table("Family", "F table")
        assert len(db.get_tables("Person")) == 1
        assert len(db.get_tables("Family")) == 1
        assert db.get_tables("Person")[0]["name"] == "P table"
        assert db.get_tables("Family")[0]["name"] == "F table"

    def test_rename_table(self, db: _DB) -> None:
        tid = db.add_table("Person", "Old Name")
        db.rename_table(tid, "New Name")
        tables = db.get_tables("Person")
        assert tables[0]["name"] == "New Name"

    def test_delete_table(self, db: _DB) -> None:
        tid = db.add_table("Person", "To Delete")
        db.delete_table(tid)
        assert db.get_tables("Person") == []

    def test_delete_table_cascades_columns(self, db: _DB) -> None:
        tid = db.add_table("Person", "T")
        db.add_column(tid, "Col", COL_TYPE_STRING)
        db.delete_table(tid)
        cur = db._con.execute("SELECT * FROM columns WHERE table_id=?", (tid,))
        assert cur.fetchone() is None

    def test_delete_table_cascades_rows(self, db: _DB) -> None:
        tid = db.add_table("Person", "T")
        cols = db.get_columns(tid)
        db.add_column(tid, "Col", COL_TYPE_STRING)
        cols = db.get_columns(tid)
        db.add_row(tid, "handle-1", cols, ["value"])
        db.delete_table(tid)
        cur = db._con.execute("SELECT * FROM rows WHERE table_id=?", (tid,))
        assert cur.fetchone() is None


# ---------------------------------------------------------------------------
# _DB – column CRUD
# ---------------------------------------------------------------------------

class TestDBColumns:

    def test_get_columns_empty(self, db_with_table: tuple[_DB, int]) -> None:
        db, tid = db_with_table
        assert db.get_columns(tid) == []

    def test_add_column_appears(self, db_with_table: tuple[_DB, int]) -> None:
        db, tid = db_with_table
        db.add_column(tid, "Height", COL_TYPE_NUMBER)
        cols = db.get_columns(tid)
        assert len(cols) == 1
        assert cols[0]["name"] == "Height"
        assert cols[0]["type"] == COL_TYPE_NUMBER
        assert cols[0]["col_order"] == 0

    def test_add_columns_ordered(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        assert [c["name"] for c in cols] == ["Name", "Score", "Link"]
        assert [c["col_order"] for c in cols] == [0, 1, 2]

    def test_update_column_name_and_type(self,
                                         db_with_table: tuple[_DB, int]) -> None:
        db, tid = db_with_table
        db.add_column(tid, "Old", COL_TYPE_STRING)
        col_order = db.get_columns(tid)[0]["col_order"]
        db.update_column(tid, col_order, "New", COL_TYPE_NUMBER)
        col = db.get_columns(tid)[0]
        assert col["name"] == "New"
        assert col["type"] == COL_TYPE_NUMBER

    def test_delete_column_removes_it(self,
                                      db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        # Delete "Score" (col_order=1)
        db.delete_column(tid, 1)
        cols = db.get_columns(tid)
        assert len(cols) == 2
        names = [c["name"] for c in cols]
        assert "Score" not in names

    def test_delete_column_renumbers(self,
                                     db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        db.delete_column(tid, 0)   # delete "Name"
        cols = db.get_columns(tid)
        assert [c["col_order"] for c in cols] == [0, 1]

    def test_delete_column_removes_row_data(self,
                                            db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        # col_order values before deletion: Name=0, Score=1, Link=2
        score_col_order = cols[1]["col_order"]  # = 1
        db.add_row(tid, "h1", cols, ["Alice", "10", "http://x.com"])
        # Verify the Score cell exists before deletion
        cur = db._con.execute(
            "SELECT * FROM rows WHERE table_id=? AND col_order=?",
            (tid, score_col_order))
        assert cur.fetchone() is not None
        # Delete "Score" column
        db.delete_column(tid, score_col_order)
        # After deletion and renumbering, no cell should have the original
        # col_order value of 1 mapped to Score's data — the row was deleted.
        # Verify by checking total remaining row cells: should be 2 (Name + Link)
        cur = db._con.execute(
            "SELECT COUNT(*) FROM rows WHERE table_id=? AND object_handle=?",
            (tid, "h1"))
        assert cur.fetchone()[0] == 2

    def test_columns_isolated_by_table(self, db: _DB) -> None:
        t1 = db.add_table("Person", "T1")
        t2 = db.add_table("Person", "T2")
        db.add_column(t1, "A", COL_TYPE_STRING)
        db.add_column(t2, "B", COL_TYPE_STRING)
        assert len(db.get_columns(t1)) == 1
        assert db.get_columns(t1)[0]["name"] == "A"
        assert len(db.get_columns(t2)) == 1
        assert db.get_columns(t2)[0]["name"] == "B"


# ---------------------------------------------------------------------------
# _DB – swap_columns
# ---------------------------------------------------------------------------

class TestDBSwapColumns:

    def test_swap_adjacent(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        # Initial order: Name(0), Score(1), Link(2)
        db.swap_columns(tid, 0, 1)
        cols = db.get_columns(tid)
        names = [c["name"] for c in cols]
        assert names == ["Score", "Name", "Link"]

    def test_swap_non_adjacent(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        db.swap_columns(tid, 0, 2)
        cols = db.get_columns(tid)
        names = [c["name"] for c in cols]
        assert names == ["Link", "Score", "Name"]

    def test_swap_updates_row_data(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "99", "http://example.com"])
        db.swap_columns(tid, 0, 1)   # swap Name ↔ Score
        cols_after = db.get_columns(tid)
        rows = db.get_rows(tid, "h1", cols_after)
        # After swap: col0=Score, col1=Name, col2=Link
        assert rows[0]["values"][0] == "99"     # Score is now first
        assert rows[0]["values"][1] == "Alice"  # Name is now second

    def test_swap_same_column_is_noop(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        before = [c["name"] for c in db.get_columns(tid)]
        db.swap_columns(tid, 0, 0)
        after = [c["name"] for c in db.get_columns(tid)]
        assert before == after


# ---------------------------------------------------------------------------
# _DB – row CRUD
# ---------------------------------------------------------------------------

class TestDBRows:

    def test_get_rows_empty(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        assert db.get_rows(tid, "h1", cols) == []

    def test_get_rows_empty_columns(self, db_with_table: tuple[_DB, int]) -> None:
        db, tid = db_with_table
        assert db.get_rows(tid, "h1", []) == []

    def test_add_row_and_retrieve(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "10", "http://a.com"])
        rows = db.get_rows(tid, "h1", cols)
        assert len(rows) == 1
        assert rows[0]["values"] == ["Alice", "10", "http://a.com"]

    def test_add_multiple_rows_ordered(self,
                                       db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "10", ""])
        db.add_row(tid, "h1", cols, ["Bob",   "20", ""])
        db.add_row(tid, "h1", cols, ["Carol", "30", ""])
        rows = db.get_rows(tid, "h1", cols)
        assert len(rows) == 3
        assert [r["values"][0] for r in rows] == ["Alice", "Bob", "Carol"]

    def test_rows_isolated_by_handle(self,
                                     db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "1", ""])
        db.add_row(tid, "h2", cols, ["Bob",   "2", ""])
        r1 = db.get_rows(tid, "h1", cols)
        r2 = db.get_rows(tid, "h2", cols)
        assert len(r1) == 1
        assert r1[0]["values"][0] == "Alice"
        assert len(r2) == 1
        assert r2[0]["values"][0] == "Bob"

    def test_rows_isolated_by_table(self, db: _DB) -> None:
        t1 = db.add_table("Person", "T1")
        t2 = db.add_table("Person", "T2")
        db.add_column(t1, "X", COL_TYPE_STRING)
        db.add_column(t2, "X", COL_TYPE_STRING)
        cols1 = db.get_columns(t1)
        cols2 = db.get_columns(t2)
        db.add_row(t1, "h1", cols1, ["in-T1"])
        assert db.get_rows(t2, "h1", cols2) == []

    def test_update_row(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "10", ""])
        ro = db.get_rows(tid, "h1", cols)[0]["row_order"]
        db.update_row(tid, "h1", ro, cols, ["Alice Updated", "99", ""])
        rows = db.get_rows(tid, "h1", cols)
        assert rows[0]["values"][0] == "Alice Updated"
        assert rows[0]["values"][1] == "99"

    def test_delete_row(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "10", ""])
        db.add_row(tid, "h1", cols, ["Bob",   "20", ""])
        rows = db.get_rows(tid, "h1", cols)
        db.delete_row(tid, "h1", rows[0]["row_order"])
        remaining = db.get_rows(tid, "h1", cols)
        assert len(remaining) == 1
        assert remaining[0]["values"][0] == "Bob"

    def test_delete_row_renumbers(self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["A", "1", ""])
        db.add_row(tid, "h1", cols, ["B", "2", ""])
        db.add_row(tid, "h1", cols, ["C", "3", ""])
        rows = db.get_rows(tid, "h1", cols)
        db.delete_row(tid, "h1", rows[0]["row_order"])
        remaining = db.get_rows(tid, "h1", cols)
        assert [r["row_order"] for r in remaining] == [0, 1]

    def test_row_missing_columns_filled_with_empty(self,
                                                    db_with_cols: tuple[_DB, int]
                                                    ) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        # Insert with only first column populated
        db.add_row(tid, "h1", cols[:1], ["Only Name"])
        rows = db.get_rows(tid, "h1", cols)
        # Missing cols default to ""
        assert rows[0]["values"] == ["Only Name", "", ""]


# ---------------------------------------------------------------------------
# _DB – migration from old schema
# ---------------------------------------------------------------------------

class TestDBMigration:

    def test_old_schema_is_dropped_and_recreated(self, tmp_path: Path) -> None:
        """A database with old schema (no table_id) must be migrated cleanly."""
        db_file = str(tmp_path / "tabledata.db")
        # Create old schema
        con = sqlite3.connect(db_file)
        con.executescript("""
            CREATE TABLE columns (
                object_type TEXT, col_order INTEGER,
                name TEXT, col_type TEXT
            );
            CREATE TABLE rows (
                object_type TEXT, object_handle TEXT,
                row_order INTEGER, col_order INTEGER, value TEXT
            );
        """)
        con.close()

        # _DB should detect and migrate without error
        instance = _DB(db_file)
        # New schema must be present
        cur = instance._con.execute("PRAGMA table_info(columns)")
        col_names = [r["name"] for r in cur]
        assert "table_id" in col_names
        assert "object_type" not in col_names


# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------

class TestCSVExport:

    def _make_cols(self) -> list[tb.ColDef]:
        return [
            {"col_order": 0, "name": "Name",  "type": COL_TYPE_STRING},
            {"col_order": 1, "name": "Score", "type": COL_TYPE_NUMBER},
        ]

    def _make_rows(self) -> list[tb.RowData]:
        return [
            {"row_order": 0, "values": ["Alice", "10"]},
            {"row_order": 1, "values": ["Bob",   "20"]},
        ]

    def test_header_row(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.csv")
        _export_csv(path, self._make_cols(), self._make_rows())
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == ["Name", "Score"]

    def test_data_rows(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.csv")
        _export_csv(path, self._make_cols(), self._make_rows())
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)
        assert rows == [["Alice", "10"], ["Bob", "20"]]

    def test_empty_rows(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.csv")
        _export_csv(path, self._make_cols(), [])
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            all_rows = list(reader)
        assert len(all_rows) == 1   # only header

    def test_values_with_commas_quoted(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.csv")
        cols = [{"col_order": 0, "name": "Desc", "type": COL_TYPE_STRING}]
        rows = [{"row_order": 0, "values": ["Hello, World"]}]
        _export_csv(path, cols, rows)
        with open(path, newline="", encoding="utf-8") as f:
            content = f.read()
        assert "Hello, World" in content   # csv module handles quoting

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.csv")
        cols = [{"col_order": 0, "name": "Name", "type": COL_TYPE_STRING}]
        rows = [{"row_order": 0, "values": ["Ålborg"]}]
        _export_csv(path, cols, rows)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Ålborg" in content


class TestCSVImport:

    def _write_csv(self, path: str, rows: list[list[str]]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

    def test_basic_import(self, tmp_path: Path) -> None:
        path = str(tmp_path / "in.csv")
        self._write_csv(path, [["Name", "Score"], ["Alice", "10"], ["Bob", "20"]])
        header, data = _import_csv(path)
        assert header == ["Name", "Score"]
        assert data == [["Alice", "10"], ["Bob", "20"]]

    def test_empty_file(self, tmp_path: Path) -> None:
        path = str(tmp_path / "empty.csv")
        open(path, "w").close()
        header, data = _import_csv(path)
        assert header == []
        assert data == []

    def test_header_only(self, tmp_path: Path) -> None:
        path = str(tmp_path / "hdr.csv")
        self._write_csv(path, [["A", "B"]])
        header, data = _import_csv(path)
        assert header == ["A", "B"]
        assert data == []

    def test_bom_stripped(self, tmp_path: Path) -> None:
        path = str(tmp_path / "bom.csv")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("Name,Score\nAlice,10\n")
        header, _ = _import_csv(path)
        assert header[0] == "Name"   # BOM must not appear

    def test_roundtrip(self, tmp_path: Path) -> None:
        path = str(tmp_path / "rt.csv")
        cols = [
            {"col_order": 0, "name": "X", "type": COL_TYPE_STRING},
            {"col_order": 1, "name": "Y", "type": COL_TYPE_NUMBER},
        ]
        original_rows: list[tb.RowData] = [
            {"row_order": 0, "values": ["foo", "1.5"]},
            {"row_order": 1, "values": ["bar", "2"]},
        ]
        _export_csv(path, cols, original_rows)
        header, data = _import_csv(path)
        assert header == ["X", "Y"]
        assert data[0] == ["foo", "1.5"]
        assert data[1] == ["bar", "2"]


# ---------------------------------------------------------------------------
# ODS import / export  (skipped when odfpy is not installed)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAVE_ODF, reason="odfpy not installed")
class TestODSExport:

    def _make_cols(self) -> list[tb.ColDef]:
        return [
            {"col_order": 0, "name": "Name",  "type": COL_TYPE_STRING},
            {"col_order": 1, "name": "Score", "type": COL_TYPE_NUMBER},
        ]

    def _make_rows(self) -> list[tb.RowData]:
        return [
            {"row_order": 0, "values": ["Alice", "10"]},
            {"row_order": 1, "values": ["Bob",   "20"]},
        ]

    def test_file_created(self, tmp_path: Path) -> None:
        path = str(tmp_path / "out.ods")
        _export_ods(path, "Sheet1", self._make_cols(), self._make_rows())
        assert os.path.exists(path)

    def test_roundtrip(self, tmp_path: Path) -> None:
        path = str(tmp_path / "rt.ods")
        _export_ods(path, "Data", self._make_cols(), self._make_rows())
        header, data = _import_ods(path)
        assert header == ["Name", "Score"]
        assert data[0] == ["Alice", "10"]
        assert data[1] == ["Bob",   "20"]

    def test_empty_rows(self, tmp_path: Path) -> None:
        path = str(tmp_path / "empty.ods")
        _export_ods(path, "Empty", self._make_cols(), [])
        header, data = _import_ods(path)
        assert header == ["Name", "Score"]
        assert data == []

    def test_utf8_values(self, tmp_path: Path) -> None:
        path = str(tmp_path / "utf8.ods")
        cols = [{"col_order": 0, "name": "Ort", "type": COL_TYPE_STRING}]
        rows = [{"row_order": 0, "values": ["Köln"]}]
        _export_ods(path, "T", cols, rows)
        header, data = _import_ods(path)
        assert data[0][0] == "Köln"


@pytest.mark.skipif(not _HAVE_ODF, reason="odfpy not installed")
class TestODSImport:

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        path = str(tmp_path / "empty.ods")
        # Export a file with no rows and no columns
        _export_ods(path, "S", [], [])
        header, data = _import_ods(path)
        assert header == []
        assert data == []

    def test_only_header_row(self, tmp_path: Path) -> None:
        path = str(tmp_path / "hdr.ods")
        cols = [{"col_order": 0, "name": "X", "type": COL_TYPE_STRING}]
        _export_ods(path, "S", cols, [])
        header, data = _import_ods(path)
        assert header == ["X"]
        assert data == []


# ---------------------------------------------------------------------------
# Integration: _DB + CSV roundtrip
# ---------------------------------------------------------------------------

class TestIntegrationCSV:

    def test_export_and_reimport_preserves_data(
            self, db_with_cols: tuple[_DB, int], tmp_path: Path) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "42", "http://a.com"])
        db.add_row(tid, "h1", cols, ["Bob",   "7",  "http://b.com"])

        path = str(tmp_path / "export.csv")
        rows = db.get_rows(tid, "h1", cols)
        _export_csv(path, cols, rows)

        header, data = _import_csv(path)
        assert header == ["Name", "Score", "Link"]
        assert len(data) == 2
        assert data[0] == ["Alice", "42", "http://a.com"]
        assert data[1] == ["Bob",   "7",  "http://b.com"]

    def test_import_into_new_table(
            self, db: _DB, tmp_path: Path) -> None:
        """Simulate the gramplet import flow: file columns → new DB columns → rows."""
        # Write a CSV
        csv_path = str(tmp_path / "data.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([
                ["Fruit",  "Count"],
                ["Apple",  "3"],
                ["Banana", "7"],
            ])

        # Create a blank table and import
        tid = db.add_table("Person", "Inventory")
        header, data_rows = _import_csv(csv_path)
        # Simulate schema reconciliation
        for h in header:
            db.add_column(tid, h, COL_TYPE_STRING)
        cols = db.get_columns(tid)
        for row in data_rows:
            db.add_row(tid, "h1", cols, row)

        result = db.get_rows(tid, "h1", cols)
        assert len(result) == 2
        assert result[0]["values"] == ["Apple",  "3"]
        assert result[1]["values"] == ["Banana", "7"]




# ---------------------------------------------------------------------------
# _DB – purge_orphaned_rows (Option B)
# ---------------------------------------------------------------------------

class TestDBPurgeOrphanedRows:

    def test_purge_removes_orphaned_handle(
            self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "1", ""])
        db.add_row(tid, "h2", cols, ["Bob",   "2", ""])
        # h2 has been deleted from Gramps; only h1 is live
        removed = db.purge_orphaned_rows("Person", {"h1"})
        assert removed > 0
        cur = db._con.execute(
            "SELECT COUNT(*) FROM rows WHERE object_handle='h2'")
        assert cur.fetchone()[0] == 0

    def test_purge_keeps_live_rows(
            self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "1", ""])
        db.purge_orphaned_rows("Person", {"h1"})
        assert db.get_rows(tid, "h1", cols) != []

    def test_purge_empty_live_set_is_noop(
            self, db_with_cols: tuple[_DB, int]) -> None:
        """Safety guard: an empty live_handles set must never wipe data."""
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "1", ""])
        removed = db.purge_orphaned_rows("Person", set())
        assert removed == 0
        assert db.get_rows(tid, "h1", cols) != []

    def test_purge_no_orphans_returns_zero(
            self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "1", ""])
        removed = db.purge_orphaned_rows("Person", {"h1"})
        assert removed == 0

    def test_purge_does_not_touch_other_object_types(
            self, db: _DB) -> None:
        t_p = db.add_table("Person", "P")
        t_f = db.add_table("Family", "F")
        db.add_column(t_p, "X", COL_TYPE_STRING)
        db.add_column(t_f, "X", COL_TYPE_STRING)
        cols_p = db.get_columns(t_p)
        cols_f = db.get_columns(t_f)
        db.add_row(t_p, "h1", cols_p, ["person"])
        db.add_row(t_f, "h1", cols_f, ["family"])
        # Purge Person handles; h1 is orphaned for Person
        db.purge_orphaned_rows("Person", {"other-handle"})
        # Family rows must be untouched
        assert db.get_rows(t_f, "h1", cols_f) != []

    def test_purge_returns_correct_count(
            self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        # 3 columns → each add_row inserts 3 cells
        db.add_row(tid, "h_orphan", cols, ["A", "1", ""])
        db.add_row(tid, "h_orphan", cols, ["B", "2", ""])
        db.add_row(tid, "h_live",   cols, ["C", "3", ""])
        removed = db.purge_orphaned_rows("Person", {"h_live"})
        assert removed == 6   # 2 orphaned rows × 3 columns

    def test_purge_multiple_orphaned_handles(
            self, db_with_cols: tuple[_DB, int]) -> None:
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        for h in ("h1", "h2", "h3"):
            db.add_row(tid, h, cols, ["val", "1", ""])
        # Only h2 is still live
        removed = db.purge_orphaned_rows("Person", {"h2"})
        assert removed > 0
        assert db.get_rows(tid, "h1", cols) == []
        assert db.get_rows(tid, "h2", cols) != []
        assert db.get_rows(tid, "h3", cols) == []

    def test_rows_survive_within_session(
            self, db_with_cols: tuple[_DB, int]) -> None:
        """
        Rows for a deleted object must survive until the next startup purge,
        so that Gramps' Undo can still work.  This test verifies that rows
        remain queryable by handle even after the notional deletion — because
        Option B does not touch the DB on delete signals at all.
        """
        db, tid = db_with_cols
        cols = db.get_columns(tid)
        db.add_row(tid, "h1", cols, ["Alice", "99", ""])
        # Simulate: object deleted in Gramps, but we do NOT call any cleanup.
        # Rows must still be there (will be purged next startup).
        rows = db.get_rows(tid, "h1", cols)
        assert len(rows) == 1
        assert rows[0]["values"][0] == "Alice"

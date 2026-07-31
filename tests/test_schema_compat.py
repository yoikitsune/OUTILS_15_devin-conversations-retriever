"""Tests for Devin Local schema compatibility (Phase 3.3).

Tests the ``scripts/check_devin_schema.py`` logic and the schema version
detection in ``devin_local.py``. These tests run in CI to catch schema
drift early — if Devin Desktop ships a new migration, these tests will
detect it and flag whether dcr needs updating.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Import the check_schema function from the script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_devin_schema import check_schema, format_report, REQUIRED_TABLES  # noqa: E402

from dcr.devin_local import (
    DEFAULT_DEVIN_LOCAL_DB,
    KNOWN_SCHEMA_VERSION,
    DevinLocalReader,
)
from tests.test_devin_local import _build_sessions_db, _sample_session


# --- Fixtures ---


@pytest.fixture
def synthetic_db(tmp_path: Path) -> Path:
    """Create a synthetic sessions.db with the known schema."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    return db_path


@pytest.fixture
def real_db() -> Path | None:
    """Return the real Devin Local sessions.db path if it exists."""
    if DEFAULT_DEVIN_LOCAL_DB.exists():
        return DEFAULT_DEVIN_LOCAL_DB
    return None


# --- check_schema function tests ---


def test_check_schema_ok(synthetic_db: Path):
    """check_schema returns status=ok for a compatible synthetic DB."""
    report = check_schema(synthetic_db)
    assert report["status"] == "ok"
    assert report["schema_version"] == KNOWN_SCHEMA_VERSION
    assert report["exists"] is True
    assert report["chat_message_keys_ok"] is True
    for table, info in report["tables"].items():
        assert info["ok"], f"{table} missing: {info['missing_columns']}"
    assert report["errors"] == []


def test_check_schema_not_found(tmp_path: Path):
    """check_schema returns status=not_found for missing DB."""
    report = check_schema(tmp_path / "nonexistent.db")
    assert report["status"] == "not_found"
    assert report["exists"] is False


def test_check_schema_ahead(tmp_path: Path):
    """check_schema returns status=ahead when version > KNOWN_SCHEMA_VERSION."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    # Bump version above known.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE refinery_schema_history SET version = ?",
        (KNOWN_SCHEMA_VERSION + 3,),
    )
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "ahead"
    assert report["schema_version"] == KNOWN_SCHEMA_VERSION + 3
    assert len(report["warnings"]) > 0
    assert "ahead" in report["warnings"][0].lower()


def test_check_schema_missing_table(tmp_path: Path):
    """check_schema returns status=incompatible when a required table is missing."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    # Drop message_nodes.
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE message_nodes")
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "incompatible"
    assert not report["tables"]["message_nodes"]["ok"]
    assert any("message_nodes" in e for e in report["errors"])


def test_check_schema_missing_column(tmp_path: Path):
    """check_schema detects missing columns in a required table."""
    db_path = tmp_path / "sessions.db"
    # Build a DB with sessions table missing 'metadata' column.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        f"""CREATE TABLE refinery_schema_history (
            version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT
        );
        INSERT INTO refinery_schema_history VALUES ({KNOWN_SCHEMA_VERSION}, 'test', '2026');
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            model TEXT,
            agent_mode TEXT,
            working_directory TEXT,
            created_at INTEGER,
            last_activity_at INTEGER,
            main_chain_id INTEGER
            -- missing: metadata
        );
        CREATE TABLE message_nodes (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT, node_id INTEGER, parent_node_id INTEGER,
            chat_message TEXT, created_at INTEGER, metadata TEXT
        );"""
    )
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "incompatible"
    assert "metadata" in report["tables"]["sessions"]["missing_columns"]


def test_check_schema_bad_chat_message_json(tmp_path: Path):
    """check_schema detects when chat_message JSON lacks required keys."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    # Corrupt a chat_message to remove 'role' and 'content'.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE message_nodes SET chat_message = '{}' WHERE row_id = 1"
    )
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "incompatible"
    assert report["chat_message_keys_ok"] is False


def test_check_schema_empty_message_nodes(tmp_path: Path):
    """check_schema handles empty message_nodes table gracefully."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [])  # no sessions → no nodes
    report = check_schema(db_path)
    # No rows to sample → chat_message_keys_ok is None, status stays ok
    assert report["chat_message_keys_ok"] is None
    assert report["status"] == "ok"


def test_format_report_human_readable(synthetic_db: Path):
    """format_report produces human-readable output."""
    report = check_schema(synthetic_db)
    text = format_report(report)
    assert "Devin Local schema check" in text
    assert "✓" in text
    assert str(KNOWN_SCHEMA_VERSION) in text


def test_format_report_not_found(tmp_path: Path):
    """format_report handles not_found status."""
    report = check_schema(tmp_path / "nope.db")
    text = format_report(report)
    assert "not found" in text


# --- Exit code tests (simulating main()) ---


def test_exit_code_ok(synthetic_db: Path):
    """Exit code 0 for compatible schema."""
    report = check_schema(synthetic_db)
    assert report["status"] == "ok"
    # main() returns 0 for ok
    assert report["status"] != "incompatible"
    assert report["status"] != "ahead"


def test_exit_code_ahead(tmp_path: Path):
    """Exit code 1 for ahead schema (warning)."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE refinery_schema_history SET version = ?", (KNOWN_SCHEMA_VERSION + 1,))
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "ahead"
    # main() returns 1 for ahead


def test_exit_code_incompatible(tmp_path: Path):
    """Exit code 2 for incompatible schema."""
    report = check_schema(tmp_path / "nonexistent.db")
    # not_found → exit 0 (it's OK to not have sessions.db)
    assert report["status"] == "not_found"

    # But missing table → exit 2
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE sessions")
    conn.commit()
    conn.close()
    report = check_schema(db_path)
    assert report["status"] == "incompatible"


# --- devin_local.py schema_version tests ---


def test_reader_schema_version_matches_known(synthetic_db: Path):
    """DevinLocalReader.schema_version() returns the known version."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        assert reader.schema_version() == KNOWN_SCHEMA_VERSION


def test_known_schema_version_is_positive():
    """KNOWN_SCHEMA_VERSION is a positive integer."""
    assert KNOWN_SCHEMA_VERSION > 0
    assert isinstance(KNOWN_SCHEMA_VERSION, int)


def test_required_tables_covers_all_dcr_reads():
    """REQUIRED_TABLES covers all tables that devin_local.py reads from."""
    # devin_local.py reads: sessions, message_nodes, refinery_schema_history
    assert "sessions" in REQUIRED_TABLES
    assert "message_nodes" in REQUIRED_TABLES
    assert "refinery_schema_history" in REQUIRED_TABLES
    # It does NOT read tool_call_state (we chose option 1 in Phase 2)
    assert "tool_call_state" not in REQUIRED_TABLES


# --- Real data tests ---


def test_real_check_schema(real_db: Path | None):
    """check_schema works on the real sessions.db."""
    if real_db is None:
        pytest.skip("No Devin Local sessions.db available")
    report = check_schema(real_db)
    # Real DB should be ok or ahead (if Devin Desktop updated)
    assert report["status"] in ("ok", "ahead")
    assert report["schema_version"] is not None
    # All required tables should be present
    for table, info in report["tables"].items():
        assert info["ok"], f"Real DB missing {table} columns: {info['missing_columns']}"


def test_real_schema_version_matches_known(real_db: Path | None):
    """The real sessions.db schema version matches what dcr was built against.

    If this test fails, it means Devin Desktop shipped a new migration.
    Update KNOWN_SCHEMA_VERSION in devin_local.py after verifying compatibility.
    """
    if real_db is None:
        pytest.skip("No Devin Local sessions.db available")
    with DevinLocalReader(db_path=real_db) as reader:
        version = reader.schema_version()
    assert version is not None
    if version > KNOWN_SCHEMA_VERSION:
        pytest.fail(
            f"Devin Local schema version {version} is ahead of known "
            f"{KNOWN_SCHEMA_VERSION}. Run `python scripts/check_devin_schema.py` "
            f"to verify compatibility, then update KNOWN_SCHEMA_VERSION in "
            f"src/dcr/devin_local.py if compatible."
        )

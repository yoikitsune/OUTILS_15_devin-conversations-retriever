"""Tests for Devin Local integration in dcr.indexer.

Covers _sync_devin_local(), sync() auto-dispatch, schema migration
(source_type, agent_mode, credit_cost, acu_cost, role, thinking, etc.),
and full-tree indexing + archival.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dcr.indexer import Indexer
from dcr.devin_local import DEFAULT_DEVIN_LOCAL_DB, KNOWN_SCHEMA_VERSION

# Re-use the synthetic DB builder from test_devin_local.
from tests.test_devin_local import _build_sessions_db, _sample_session

NO_CASCADE = Path("/nonexistent/cascade-dir")


# --- Fixtures ---


@pytest.fixture
def indexer(tmp_path: Path) -> Indexer:
    """Create a fresh indexer with a temp database."""
    idx = Indexer(db_path=tmp_path / "test.db")
    idx.init_schema()
    yield idx
    idx.close()


@pytest.fixture
def synthetic_devin_db(tmp_path: Path) -> Path:
    """Create a synthetic sessions.db with one sample session."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    return db_path


# --- Schema migration tests ---


def test_schema_has_source_type_column(indexer: Indexer):
    """The conversations table has a source_type column after init_schema."""
    cur = indexer.conn.execute("PRAGMA table_info(conversations)")
    columns = {row[1] for row in cur.fetchall()}
    assert "source_type" in columns
    assert "agent_mode" in columns
    assert "credit_cost" in columns
    assert "acu_cost" in columns


def test_schema_has_step_enrichment_columns(indexer: Indexer):
    """The steps table has Devin Local enrichment columns after init_schema."""
    cur = indexer.conn.execute("PRAGMA table_info(steps)")
    columns = {row[1] for row in cur.fetchall()}
    assert "role" in columns
    assert "thinking" in columns
    assert "tool_calls_json" in columns
    assert "tool_call_id" in columns
    assert "node_id" in columns
    assert "parent_node_id" in columns
    assert "on_main_chain" in columns


def test_schema_migration_idempotent(tmp_path: Path):
    """init_schema can be called twice without error (idempotent migration)."""
    idx = Indexer(db_path=tmp_path / "test.db")
    idx.init_schema()
    idx.init_schema()  # should not raise
    idx.close()


def test_schema_migration_on_existing_db(tmp_path: Path):
    """Migrations add new columns to an existing (pre-ADR-0005) database."""
    db_path = tmp_path / "legacy.db"
    # Create a legacy DB matching the pre-ADR-0005 schema (all original
    # columns + archived/archived_at from B2/B3, but NO ADR-0005 columns).
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cascade_id TEXT UNIQUE NOT NULL,
            trajectory_id TEXT,
            title TEXT,
            trajectory_type INTEGER,
            source INTEGER,
            project_path TEXT,
            git_branch TEXT,
            model TEXT,
            created_at REAL,
            updated_at REAL,
            step_count INTEGER DEFAULT 0,
            round_count INTEGER DEFAULT 0,
            checkpoint_count INTEGER DEFAULT 0,
            pb_mtime REAL DEFAULT 0,
            pb_size INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            archived_at TEXT,
            indexed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            type INTEGER,
            status INTEGER,
            variant_field INTEGER,
            content_text TEXT,
            timestamp REAL,
            model TEXT
        );
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            prompt TEXT,
            start_step INTEGER,
            end_step INTEGER
        );
        CREATE TABLE checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            checkpoint_index INTEGER,
            user_intent TEXT,
            session_summary TEXT,
            code_change_summary TEXT,
            memory_summary TEXT,
            conversation_title TEXT,
            plan_snapshot TEXT,
            intent_only INTEGER DEFAULT 0,
            included_step_index_start INTEGER,
            included_step_index_end INTEGER,
            edited_files TEXT
        );
        CREATE VIRTUAL TABLE steps_fts USING fts5(
            content_text, content='steps', content_rowid='id', tokenize='unicode61'
        );
        CREATE TRIGGER steps_ai AFTER INSERT ON steps BEGIN
            INSERT INTO steps_fts(rowid, content_text) VALUES (new.id, new.content_text);
        END;
        CREATE TRIGGER steps_ad AFTER DELETE ON steps BEGIN
            INSERT INTO steps_fts(steps_fts, rowid, content_text) VALUES ('delete', old.id, old.content_text);
        END;
        CREATE TRIGGER steps_au AFTER UPDATE ON steps BEGIN
            INSERT INTO steps_fts(steps_fts, rowid, content_text) VALUES ('delete', old.id, old.content_text);
            INSERT INTO steps_fts(rowid, content_text) VALUES (new.id, new.content_text);
        END;"""
    )
    conn.commit()
    conn.close()
    # Now init_schema should migrate it (add ADR-0005 columns).
    idx = Indexer(db_path=db_path)
    idx.init_schema()
    cur = idx.conn.execute("PRAGMA table_info(conversations)")
    columns = {row[1] for row in cur.fetchall()}
    assert "source_type" in columns
    assert "agent_mode" in columns
    assert "credit_cost" in columns
    assert "acu_cost" in columns
    cur = idx.conn.execute("PRAGMA table_info(steps)")
    columns = {row[1] for row in cur.fetchall()}
    assert "role" in columns
    assert "thinking" in columns
    assert "tool_calls_json" in columns
    assert "on_main_chain" in columns
    idx.close()


# --- _sync_devin_local tests ---


def test_sync_devin_local_indexes_session(indexer: Indexer, synthetic_devin_db: Path):
    """_sync_devin_local indexes a Devin Local session."""
    result = indexer._sync_devin_local(synthetic_devin_db)
    assert result["new"] == 1
    assert result["failed"] == 0
    status = indexer.get_status()
    assert status["conversation_count"] == 1
    assert status["sources"]["devin_local"]["conversation_count"] == 1


def test_sync_devin_local_full_tree(indexer: Indexer, synthetic_devin_db: Path):
    """_sync_devin_local indexes ALL nodes (full-tree), including lateral branches."""
    indexer._sync_devin_local(synthetic_devin_db)
    conv = indexer.get_conversation("test-slug")
    assert conv is not None
    assert conv["source_type"] == "devin_local"
    assert conv["agent_mode"] == "bypass"
    assert conv["credit_cost"] == 1.5
    assert conv["acu_cost"] == 0.25
    # Full tree: 7 nodes.
    assert len(conv["steps"]) == 7
    # Lateral branch node 5 is present.
    node_ids = [s["node_id"] for s in conv["steps"]]
    assert 5 in node_ids


def test_sync_devin_local_thinking_stored(indexer: Indexer, synthetic_devin_db: Path):
    """thinking is stored in the steps table."""
    indexer._sync_devin_local(synthetic_devin_db)
    cur = indexer.conn.execute(
        "SELECT thinking FROM steps WHERE thinking IS NOT NULL"
    )
    thinkings = [row[0] for row in cur.fetchall()]
    assert "I should suggest pytest." in thinkings
    assert "Maybe unittest is better." in thinkings


def test_sync_devin_local_tool_calls_stored(indexer: Indexer, synthetic_devin_db: Path):
    """tool_calls_json is stored in the steps table."""
    indexer._sync_devin_local(synthetic_devin_db)
    cur = indexer.conn.execute(
        "SELECT tool_calls_json FROM steps WHERE tool_calls_json IS NOT NULL"
    )
    row = cur.fetchone()
    assert row is not None
    calls = json.loads(row[0])
    assert calls[0]["name"] == "read"


def test_sync_devin_local_checkpoints(indexer: Indexer, synthetic_devin_db: Path):
    """Compaction nodes are stored as checkpoints."""
    indexer._sync_devin_local(synthetic_devin_db)
    conv = indexer.get_conversation("test-slug")
    assert len(conv["checkpoints"]) == 1
    cp = conv["checkpoints"][0]
    assert cp["session_summary"] == "compacted system prompt"


def test_sync_devin_local_incremental(indexer: Indexer, synthetic_devin_db: Path):
    """_sync_devin_local is incremental on last_activity_at (skips unchanged)."""
    indexer._sync_devin_local(synthetic_devin_db)
    result = indexer._sync_devin_local(synthetic_devin_db)
    assert result["new"] == 0
    assert result["updated"] == 0
    assert result["unchanged"] == 1


def test_sync_devin_local_detects_updated(indexer: Indexer, synthetic_devin_db: Path):
    """_sync_devin_local re-indexes when last_activity_at changes."""
    indexer._sync_devin_local(synthetic_devin_db)
    # Bump last_activity_at and title.
    conn = sqlite3.connect(str(synthetic_devin_db))
    conn.execute(
        "UPDATE sessions SET last_activity_at = ?, title = ? WHERE id = ?",
        (1785009999, "Updated Title", "test-slug"),
    )
    conn.commit()
    conn.close()
    result = indexer._sync_devin_local(synthetic_devin_db)
    assert result["updated"] == 1
    conv = indexer.get_conversation("test-slug")
    assert conv["title"] == "Updated Title"


def test_sync_devin_local_archives_deleted(indexer: Indexer, synthetic_devin_db: Path):
    """_sync_devin_local archives sessions no longer in sessions.db (never deletes)."""
    indexer._sync_devin_local(synthetic_devin_db)
    assert indexer.get_status()["conversation_count"] == 1
    # Delete the session from sessions.db.
    conn = sqlite3.connect(str(synthetic_devin_db))
    conn.execute("DELETE FROM message_nodes WHERE session_id = 'test-slug'")
    conn.execute("DELETE FROM sessions WHERE id = 'test-slug'")
    conn.commit()
    conn.close()
    result = indexer._sync_devin_local(synthetic_devin_db)
    assert result["archived"] == 1
    # Conversation is still in the DB, marked archived.
    assert indexer.get_status()["conversation_count"] == 1
    assert indexer.get_status()["archived_count"] == 1
    conv = indexer.get_conversation("test-slug")
    assert conv["archived"] == 1


def test_sync_devin_local_missing_db(indexer: Indexer, tmp_path: Path):
    """_sync_devin_local returns empty result when sessions.db doesn't exist."""
    result = indexer._sync_devin_local(tmp_path / "nonexistent.db")
    assert result["new"] == 0
    assert result["archived"] == 0
    assert result["failed"] == 0


def test_sync_devin_local_stable_id_across_reindex(indexer: Indexer, synthetic_devin_db: Path):
    """Re-indexing a Devin Local session preserves its numeric DB id (B4 fix)."""
    indexer._sync_devin_local(synthetic_devin_db)
    conv = indexer.get_conversation("test-slug")
    original_id = conv["id"]
    # Force re-index by bumping last_activity_at.
    conn = sqlite3.connect(str(synthetic_devin_db))
    conn.execute("UPDATE sessions SET last_activity_at = 1785009999 WHERE id = 'test-slug'")
    conn.commit()
    conn.close()
    indexer._sync_devin_local(synthetic_devin_db)
    conv = indexer.get_conversation("test-slug")
    assert conv["id"] == original_id


# --- sync() auto-dispatch tests ---


def test_sync_dispatches_both_sources(indexer: Indexer, synthetic_devin_db: Path, tmp_path: Path):
    """sync() indexes both Cascade (empty) and Devin Local."""
    empty_cascade = tmp_path / "empty_cascade"
    empty_cascade.mkdir()
    result = indexer.sync(cascade_dir=empty_cascade, devin_local_db=synthetic_devin_db)
    assert result["new"] == 1  # 1 Devin Local session
    assert result["sources"]["devin_local"]["new"] == 1
    assert result["sources"]["cascade"]["new"] == 0


def test_sync_missing_both_sources(indexer: Indexer, tmp_path: Path):
    """sync() with both sources missing returns all zeros (no crash)."""
    result = indexer.sync(
        cascade_dir=tmp_path / "no_cascade",
        devin_local_db=tmp_path / "no_devin.db",
    )
    assert result["new"] == 0
    assert result["archived"] == 0
    assert result["failed"] == 0


def test_sync_aggregates_counts(indexer: Indexer, synthetic_devin_db: Path, tmp_path: Path):
    """sync() top-level counts aggregate both sources."""
    empty_cascade = tmp_path / "empty_cascade"
    empty_cascade.mkdir()
    result = indexer.sync(cascade_dir=empty_cascade, devin_local_db=synthetic_devin_db)
    assert result["new"] == result["sources"]["cascade"]["new"] + result["sources"]["devin_local"]["new"]


# --- get_status per-source breakdown ---


def test_get_status_source_breakdown(indexer: Indexer, synthetic_devin_db: Path):
    """get_status includes per-source breakdown."""
    indexer._sync_devin_local(synthetic_devin_db)
    status = indexer.get_status()
    assert "sources" in status
    assert status["sources"]["devin_local"]["conversation_count"] == 1
    assert status["sources"]["devin_local"]["step_count"] == 7
    assert status["sources"]["cascade"]["conversation_count"] == 0


# --- FTS5 search across Devin Local content ---


def test_search_finds_devin_local_content(indexer: Indexer, synthetic_devin_db: Path):
    """FTS5 search finds content from indexed Devin Local sessions."""
    indexer._sync_devin_local(synthetic_devin_db)
    cur = indexer.conn.execute(
        "SELECT s.content_text FROM steps_fts fts JOIN steps s ON s.id = fts.rowid "
        "WHERE steps_fts MATCH 'pytest' ORDER BY rank"
    )
    rows = cur.fetchall()
    assert len(rows) >= 1
    assert "pytest" in rows[0][0].lower()


# --- Real data tests ---


@pytest.fixture
def real_devin_db() -> Path | None:
    """Return the real Devin Local sessions.db path if it exists."""
    if DEFAULT_DEVIN_LOCAL_DB.exists():
        return DEFAULT_DEVIN_LOCAL_DB
    return None


def test_real_sync_devin_local(real_devin_db: Path | None, tmp_path: Path):
    """_sync_devin_local works on the real sessions.db."""
    if real_devin_db is None:
        pytest.skip("No Devin Local sessions.db available")
    idx = Indexer(db_path=tmp_path / "real.db")
    result = idx._sync_devin_local(real_devin_db)
    assert result["failed"] == 0, f"Errors: {result['errors']}"
    assert result["new"] > 0
    status = idx.get_status()
    assert status["sources"]["devin_local"]["conversation_count"] > 0
    assert status["sources"]["devin_local"]["step_count"] > 0
    idx.close()


def test_real_sync_devin_local_incremental(real_devin_db: Path | None, tmp_path: Path):
    """Second _sync_devin_local run is incremental (unchanged)."""
    if real_devin_db is None:
        pytest.skip("No Devin Local sessions.db available")
    idx = Indexer(db_path=tmp_path / "real.db")
    idx._sync_devin_local(real_devin_db)
    result = idx._sync_devin_local(real_devin_db)
    assert result["new"] == 0
    idx.close()

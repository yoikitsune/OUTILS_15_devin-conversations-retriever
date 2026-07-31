"""Tests for dcr.devin_local module.

Covers the Devin Local SQLite reader: synthetic sessions.db for deterministic
tests, plus real-data tests (skipped if sessions.db is absent).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dcr.devin_local import (
    DEFAULT_DEVIN_LOCAL_DB,
    KNOWN_SCHEMA_VERSION,
    DevinLocalReader,
    _extract_thinking,
    _main_chain_set,
    _safe_json,
)
from dcr.parser import TrajectoryInfo


# --- Helpers to build a synthetic sessions.db ---


def _make_chat_message(
    role: str,
    content: str = "",
    thinking: str | None = None,
    tool_calls: list | None = None,
    tool_call_id: str | None = None,
) -> str:
    """Build a chat_message JSON string as Devin Local stores it."""
    msg: dict = {"message_id": f"msg-{role}-{content[:8]}", "role": role, "content": content}
    if thinking is not None:
        msg["thinking"] = {"thinking": thinking, "signature": ""}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    if tool_call_id is not None:
        msg["tool_call_id"] = tool_call_id
    msg["metadata"] = {}
    return json.dumps(msg)


def _make_node_metadata(prior_ids: list[int] | None = None) -> str:
    """Build a message_nodes.metadata JSON string."""
    ext: dict = {}
    if prior_ids is not None:
        ext["compact/prior_node_ids"] = prior_ids
    return json.dumps({"extensions": ext})


def _build_sessions_db(db_path: Path, sessions: list[dict]) -> None:
    """Create a synthetic sessions.db with the given sessions and nodes.

    Each session dict has keys: id, title, model, agent_mode, working_directory,
    created_at, last_activity_at, main_chain_id, metadata (dict), nodes (list).
    Each node has keys: node_id, parent_node_id, role, content, thinking,
    tool_calls, tool_call_id, created_at, prior_ids (optional).
    """
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE refinery_schema_history (
            version INTEGER PRIMARY KEY,
            name TEXT,
            applied_at TEXT
        );
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            working_directory TEXT NOT NULL,
            backend_type TEXT NOT NULL,
            model TEXT NOT NULL,
            agent_mode TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            last_activity_at INTEGER NOT NULL,
            title TEXT,
            main_chain_id INTEGER,
            shell_last_seen_index INTEGER DEFAULT 0,
            cogs_json TEXT,
            workspace_dirs TEXT,
            hidden INTEGER NOT NULL DEFAULT 0,
            metadata TEXT
        );
        CREATE TABLE message_nodes (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            node_id INTEGER NOT NULL,
            parent_node_id INTEGER,
            chat_message TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(session_id, node_id)
        );
        """
    )
    conn.execute(
        "INSERT INTO refinery_schema_history (version, name, applied_at) VALUES (?, ?, ?)",
        (KNOWN_SCHEMA_VERSION, "test", "2026-07-31"),
    )
    for s in sessions:
        conn.execute(
            """INSERT INTO sessions (id, working_directory, backend_type, model,
               agent_mode, created_at, last_activity_at, title, main_chain_id, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s["id"],
                s.get("working_directory", "/tmp"),
                "local",
                s.get("model", "glm-5-2"),
                s.get("agent_mode", "normal"),
                s["created_at"],
                s["last_activity_at"],
                s.get("title"),
                s.get("main_chain_id"),
                json.dumps(s.get("metadata", {})),
            ),
        )
        for n in s["nodes"]:
            conn.execute(
                """INSERT INTO message_nodes (session_id, node_id, parent_node_id,
                   chat_message, created_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    s["id"],
                    n["node_id"],
                    n.get("parent_node_id"),
                    _make_chat_message(
                        n["role"],
                        n.get("content", ""),
                        n.get("thinking"),
                        n.get("tool_calls"),
                        n.get("tool_call_id"),
                    ),
                    n["created_at"],
                    _make_node_metadata(n.get("prior_ids")),
                ),
            )
    conn.commit()
    conn.close()


def _sample_session(slug: str = "test-slug") -> dict:
    """Build a sample session with a main chain and a lateral branch."""
    return {
        "id": slug,
        "title": "Test Conversation",
        "model": "glm-5-2",
        "agent_mode": "bypass",
        "working_directory": "/home/user/project",
        "created_at": 1785000000,
        "last_activity_at": 1785000100,
        "main_chain_id": 4,  # tip → 4 → 3 → 2 → 1 → 0
        "metadata": {"total_credit_cost": 1.5, "total_acu_cost": 0.25},
        "nodes": [
            # Main chain: 0 → 1 → 2 → 3 → 4
            {"node_id": 0, "parent_node_id": None, "role": "system",
             "content": "system prompt", "created_at": 1785000000},
            {"node_id": 1, "parent_node_id": 0, "role": "user",
             "content": "How do I test?", "created_at": 1785000001},
            {"node_id": 2, "parent_node_id": 1, "role": "assistant",
             "content": "Use pytest.", "thinking": "I should suggest pytest.",
             "tool_calls": [{"id": "tc-1", "name": "read", "arguments": {"file_path": "/x"}}],
             "created_at": 1785000002},
            # Lateral branch: 5 → 2 (regeneration of node 3)
            {"node_id": 5, "parent_node_id": 2, "role": "assistant",
             "content": "Use unittest instead.", "thinking": "Maybe unittest is better.",
             "created_at": 1785000003},
            # Main chain continues: 3 → 4
            {"node_id": 3, "parent_node_id": 2, "role": "tool",
             "content": "file contents", "tool_call_id": "tc-1",
             "created_at": 1785000004},
            {"node_id": 4, "parent_node_id": 3, "role": "assistant",
             "content": "Done.", "created_at": 1785000005},
            # Compaction node: 6, parent=4, compacting node 0
            {"node_id": 6, "parent_node_id": 4, "role": "system",
             "content": "compacted system prompt", "created_at": 1785000006,
             "prior_ids": [0]},
        ],
    }


# --- Fixtures ---


@pytest.fixture
def synthetic_db(tmp_path: Path) -> Path:
    """Create a synthetic sessions.db with one sample session."""
    db_path = tmp_path / "sessions.db"
    _build_sessions_db(db_path, [_sample_session()])
    return db_path


@pytest.fixture
def real_db() -> Path | None:
    """Return the real Devin Local sessions.db path if it exists."""
    if DEFAULT_DEVIN_LOCAL_DB.exists():
        return DEFAULT_DEVIN_LOCAL_DB
    return None


# --- Helper function tests ---


def test_safe_json_none():
    """_safe_json returns {} for None input."""
    assert _safe_json(None) == {}


def test_safe_json_invalid():
    """_safe_json returns {} for invalid JSON."""
    assert _safe_json("not json") == {}


def test_safe_json_valid():
    """_safe_json parses valid JSON."""
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_non_dict():
    """_safe_json returns {} for non-dict JSON."""
    assert _safe_json("[1, 2]") == {}


def test_extract_thinking_none():
    """_extract_thinking returns None for None input."""
    assert _extract_thinking(None) is None


def test_extract_thinking_dict():
    """_extract_thinking extracts the nested .thinking key."""
    assert _extract_thinking({"thinking": "reasoning here", "signature": "x"}) == "reasoning here"


def test_extract_thinking_string():
    """_extract_thinking accepts a bare string."""
    assert _extract_thinking("bare reasoning") == "bare reasoning"


def test_extract_thinking_empty():
    """_extract_thinking returns None for empty thinking."""
    assert _extract_thinking({"thinking": "", "signature": ""}) is None
    assert _extract_thinking("") is None


def test_main_chain_set_basic():
    """_main_chain_set walks tip → root via parent_node_id."""
    parents = {0: None, 1: 0, 2: 1, 3: 2, 4: 3, 5: 2}
    chain = _main_chain_set(4, parents)
    assert chain == {0, 1, 2, 3, 4}
    # Node 5 is a lateral branch — not in the chain.
    assert 5 not in chain


def test_main_chain_set_null_tip():
    """_main_chain_set returns empty set when tip is None."""
    assert _main_chain_set(None, {0: None}) == set()


def test_main_chain_set_cycle_guard():
    """_main_chain_set does not loop forever on a cycle."""
    # 1 → 2 → 1 (cycle)
    parents = {1: 2, 2: 1}
    chain = _main_chain_set(1, parents)
    assert chain == {1, 2}


# --- DevinLocalReader tests ---


def test_reader_file_not_found(tmp_path: Path):
    """Reader raises FileNotFoundError for missing db."""
    reader = DevinLocalReader(db_path=tmp_path / "nope.db")
    with pytest.raises(FileNotFoundError):
        _ = reader.conn


def test_reader_schema_version(synthetic_db: Path):
    """Reader returns the refinery schema version."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        assert reader.schema_version() == KNOWN_SCHEMA_VERSION


def test_reader_schema_version_missing_table(tmp_path: Path):
    """schema_version returns None if refinery_schema_history is absent."""
    db_path = tmp_path / "empty.db"
    sqlite3.connect(str(db_path)).close()  # create empty db
    with DevinLocalReader(db_path=db_path) as reader:
        assert reader.schema_version() is None


def test_reader_check_schema_known(synthetic_db: Path):
    """check_schema returns the known version without warning."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        assert reader.check_schema() == KNOWN_SCHEMA_VERSION


def test_reader_check_schema_higher(tmp_path: Path):
    """check_schema warns on higher-than-known schema version."""
    db_path = tmp_path / "future.db"
    _build_sessions_db(db_path, [])
    # Bump the version above known.
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE refinery_schema_history SET version = ?", (KNOWN_SCHEMA_VERSION + 5,))
    conn.commit()
    conn.close()
    with DevinLocalReader(db_path=db_path) as reader:
        version = reader.check_schema()
    assert version == KNOWN_SCHEMA_VERSION + 5


def test_reader_list_sessions(synthetic_db: Path):
    """list_sessions returns all sessions with parsed metadata."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        sessions = reader.list_sessions()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["id"] == "test-slug"
    assert s["title"] == "Test Conversation"
    assert s["model"] == "glm-5-2"
    assert s["agent_mode"] == "bypass"
    assert s["main_chain_id"] == 4
    assert s["metadata"]["total_credit_cost"] == 1.5


def test_reader_read_session_not_found(synthetic_db: Path):
    """read_session returns None for unknown session id."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        assert reader.read_session("nonexistent") is None


def test_reader_read_session_full_tree(synthetic_db: Path):
    """read_session indexes all nodes (full-tree), not just main chain."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    assert traj is not None
    assert traj.source_type == "devin_local"
    assert traj.cascade_id == "test-slug"
    assert traj.title == "Test Conversation"
    assert traj.agent_mode == "bypass"
    assert traj.credit_cost == 1.5
    assert traj.acu_cost == 0.25
    assert traj.project_path == "/home/user/project"
    # Full tree: 7 nodes (0-6), not just the 5 main-chain nodes.
    assert len(traj.steps) == 7
    # Authoritative session-level timestamps.
    assert traj.created_at == 1785000000.0
    assert traj.updated_at == 1785000100.0


def test_reader_read_session_main_chain_flag(synthetic_db: Path):
    """on_main_chain is 1 for main-chain nodes, 0 for lateral branches."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    by_node = {s.node_id: s for s in traj.steps}
    # Main chain: tip=4 → 4 → 3 → 2 → 1 → 0. Node 6 is a lateral branch
    # off node 4 (child of the tip, but not the tip itself).
    assert by_node[0].on_main_chain == 1
    assert by_node[1].on_main_chain == 1
    assert by_node[2].on_main_chain == 1
    assert by_node[3].on_main_chain == 1
    assert by_node[4].on_main_chain == 1
    # Lateral branches: node 5 (regeneration) and node 6 (compaction child of tip)
    assert by_node[5].on_main_chain == 0
    assert by_node[6].on_main_chain == 0


def test_reader_read_session_thinking(synthetic_db: Path):
    """thinking is extracted from the nested chat_message.thinking.thinking key."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    by_node = {s.node_id: s for s in traj.steps}
    assert by_node[2].thinking == "I should suggest pytest."
    assert by_node[5].thinking == "Maybe unittest is better."
    # Nodes without thinking have None.
    assert by_node[0].thinking is None


def test_reader_read_session_tool_calls(synthetic_db: Path):
    """tool_calls_json is a JSON string of the chat_message.tool_calls array."""
    import json as _json
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    by_node = {s.node_id: s for s in traj.steps}
    assert by_node[2].tool_calls_json is not None
    calls = _json.loads(by_node[2].tool_calls_json)
    assert calls[0]["name"] == "read"
    # Nodes without tool_calls have None.
    assert by_node[0].tool_calls_json is None


def test_reader_read_session_tool_role(synthetic_db: Path):
    """tool-role nodes have tool_call_id set."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    by_node = {s.node_id: s for s in traj.steps}
    assert by_node[3].role == "tool"
    assert by_node[3].tool_call_id == "tc-1"


def test_reader_read_session_role_variant_mapping(synthetic_db: Path):
    """role → variant_field mapping mirrors Cascade variant numbers."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    by_node = {s.node_id: s for s in traj.steps}
    assert by_node[1].role == "user"
    assert by_node[1].variant_field == 19  # VARIANT_USER_INPUT
    assert by_node[2].role == "assistant"
    assert by_node[2].variant_field == 20  # VARIANT_PLANNER_RESPONSE
    assert by_node[3].role == "tool"
    assert by_node[3].variant_field == 37  # VARIANT_COMMAND_RESULT


def test_reader_read_session_compaction_checkpoints(synthetic_db: Path):
    """Compaction nodes (metadata.extensions.compact/prior_node_ids) become checkpoints."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    assert len(traj.checkpoints) == 1
    cp = traj.checkpoints[0]
    assert cp.step_index == 6  # compaction node's own node_id
    assert cp.included_step_index_start == 0  # min(prior_ids)
    assert cp.included_step_index_end == 0  # max(prior_ids)
    assert cp.session_summary == "compacted system prompt"


def test_reader_read_session_ordering(synthetic_db: Path):
    """Steps are ordered by created_at ASC, node_id ASC (not node_id alone)."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        traj = reader.read_session("test-slug")
    # Node 5 has created_at=1785000003, node 3 has created_at=1785000004.
    # So node 5 comes before node 3 despite having a higher node_id than 2.
    timestamps = [s.timestamp for s in traj.steps]
    assert timestamps == sorted(timestamps)


def test_reader_read_sessions_all(synthetic_db: Path):
    """read_sessions returns all sessions as TrajectoryInfo."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        trajs = reader.read_sessions()
    assert len(trajs) == 1
    assert isinstance(trajs[0], TrajectoryInfo)


def test_reader_read_session_null_main_chain(tmp_path: Path):
    """read_session handles NULL main_chain_id (all nodes off main chain)."""
    db_path = tmp_path / "sessions.db"
    session = _sample_session()
    session["main_chain_id"] = None
    _build_sessions_db(db_path, [session])
    with DevinLocalReader(db_path=db_path) as reader:
        traj = reader.read_session("test-slug")
    assert traj is not None
    # All nodes have on_main_chain=0 (fallback).
    assert all(s.on_main_chain == 0 for s in traj.steps)


def test_reader_read_session_empty_title(tmp_path: Path):
    """read_session falls back to derived title when session title is NULL."""
    db_path = tmp_path / "sessions.db"
    session = _sample_session()
    session["title"] = None
    _build_sessions_db(db_path, [session])
    with DevinLocalReader(db_path=db_path) as reader:
        traj = reader.read_session("test-slug")
    assert traj is not None
    # Title falls back to first user prompt.
    assert "How do I test?" in traj.title


def test_reader_readonly_mode(synthetic_db: Path):
    """Reader opens sessions.db in read-only mode."""
    with DevinLocalReader(db_path=synthetic_db) as reader:
        _ = reader.conn
        # Attempting to write should raise (read-only).
        with pytest.raises(sqlite3.OperationalError):
            reader.conn.execute("INSERT INTO sessions (id) VALUES ('x')")


# --- Real data tests ---


def test_real_reader_list_sessions(real_db: Path | None):
    """list_sessions works on the real sessions.db."""
    if real_db is None:
        pytest.skip("No Devin Local sessions.db available")
    with DevinLocalReader(db_path=real_db) as reader:
        sessions = reader.list_sessions()
    assert len(sessions) > 0


def test_real_reader_read_session(real_db: Path | None):
    """read_session produces a valid TrajectoryInfo on real data."""
    if real_db is None:
        pytest.skip("No Devin Local sessions.db available")
    with DevinLocalReader(db_path=real_db) as reader:
        sessions = reader.list_sessions()
        traj = reader.read_session(sessions[0]["id"])
    assert traj is not None
    assert traj.source_type == "devin_local"
    assert len(traj.steps) > 0
    # At least some nodes should be on the main chain.
    on_main = sum(1 for s in traj.steps if s.on_main_chain)
    assert on_main > 0

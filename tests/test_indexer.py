"""Tests for dcr.indexer module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from dcr.indexer import Indexer, DEFAULT_CASCADE_DIR
from dcr.parser import (
    CheckpointInfo,
    RoundInfo,
    StepInfo,
    TrajectoryInfo,
)
from dcr.decrypt import KEY, NONCE_SIZE, decrypt_bytes


# --- Fixtures ---


@pytest.fixture
def indexer(tmp_path: Path) -> Indexer:
    """Create a fresh indexer with a temp database."""
    idx = Indexer(db_path=tmp_path / "test.db")
    idx.init_schema()
    yield idx
    idx.close()


@pytest.fixture
def sample_trajectory() -> TrajectoryInfo:
    """Build a sample TrajectoryInfo for testing."""
    return TrajectoryInfo(
        trajectory_id="traj-uuid-001",
        cascade_id="cascade-uuid-001",
        trajectory_type=1,
        source=2,
        steps=[
            StepInfo(
                index=0,
                type=0,
                status=1,
                variant_field=19,
                content_text="How do I parse protobuf?",
            ),
            StepInfo(
                index=1,
                type=0,
                status=1,
                variant_field=20,
                content_text="You can use the protobuf library to parse wire format.",
            ),
            StepInfo(
                index=2,
                type=0,
                status=1,
                variant_field=30,
                content_text="",
            ),
        ],
        checkpoints=[
            CheckpointInfo(
                step_index=2,
                checkpoint_index=0,
                user_intent="User asked about protobuf parsing",
                session_summary="Explained protobuf wire format parsing",
                code_change_summary="No code changes",
                conversation_title="Protobuf Parsing Discussion",
            ),
        ],
        rounds=[
            RoundInfo(
                round_number=1,
                prompt="How do I parse protobuf?",
                start_step=0,
                end_step=2,
            ),
        ],
    )


@pytest.fixture
def real_pb_dir() -> Path | None:
    """Return the cascade directory if .pb files exist."""
    cascade_dir = Path.home() / ".codeium/windsurf/cascade"
    if cascade_dir.exists() and list(cascade_dir.glob("*.pb")):
        return cascade_dir
    return None


# --- Schema tests ---


def test_init_schema_creates_tables(indexer: Indexer):
    """init_schema creates all required tables."""
    cur = indexer.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    assert "conversations" in tables
    assert "rounds" in tables
    assert "steps" in tables
    assert "checkpoints" in tables
    assert "rounds_fts" in tables
    assert "steps_fts" in tables
    assert "checkpoints_fts" in tables


def test_init_schema_creates_triggers(indexer: Indexer):
    """init_schema creates FTS5 sync triggers."""
    cur = indexer.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
    )
    triggers = [row[0] for row in cur.fetchall()]
    assert "rounds_ai" in triggers
    assert "rounds_ad" in triggers
    assert "steps_ai" in triggers
    assert "steps_ad" in triggers
    assert "checkpoints_ai" in triggers
    assert "checkpoints_ad" in triggers


def test_init_schema_idempotent(indexer: Indexer):
    """Calling init_schema twice doesn't error."""
    indexer.init_schema()
    indexer.init_schema()


# --- index_trajectory tests ---


def test_index_trajectory_basic(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """Index a trajectory and verify conversation row."""
    conv_id = indexer.index_trajectory(
        sample_trajectory,
        cascade_id="cascade-uuid-001",
        pb_mtime=1000.0,
        pb_size=5000,
    )
    assert conv_id is not None
    assert conv_id > 0

    cur = indexer.conn.execute(
        "SELECT cascade_id, trajectory_id, title, step_count, round_count, "
        "checkpoint_count, pb_mtime, pb_size FROM conversations WHERE id = ?",
        (conv_id,),
    )
    row = cur.fetchone()
    assert row[0] == "cascade-uuid-001"
    assert row[1] == "traj-uuid-001"
    assert row[2] == "Protobuf Parsing Discussion"
    assert row[3] == 3  # step_count
    assert row[4] == 1  # round_count
    assert row[5] == 1  # checkpoint_count
    assert row[6] == 1000.0
    assert row[7] == 5000


def test_index_trajectory_rounds(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """Indexed rounds are correct."""
    conv_id = indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT round_number, prompt, start_step, end_step FROM rounds "
        "WHERE conversation_id = ? ORDER BY round_number",
        (conv_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1
    assert rows[0][1] == "How do I parse protobuf?"
    assert rows[0][2] == 0
    assert rows[0][3] == 2


def test_index_trajectory_steps(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """Indexed steps are correct."""
    conv_id = indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT step_index, type, variant_field, content_text FROM steps "
        "WHERE conversation_id = ? ORDER BY step_index",
        (conv_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 3
    assert rows[0][0] == 0
    assert rows[0][2] == 19
    assert rows[0][3] == "How do I parse protobuf?"
    assert rows[1][2] == 20
    assert rows[1][3] == "You can use the protobuf library to parse wire format."


def test_index_trajectory_checkpoints(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """Indexed checkpoints are correct."""
    conv_id = indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT step_index, user_intent, session_summary, conversation_title "
        "FROM checkpoints WHERE conversation_id = ?",
        (conv_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 2
    assert rows[0][1] == "User asked about protobuf parsing"
    assert rows[0][3] == "Protobuf Parsing Discussion"


def test_index_trajectory_upsert(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """Re-indexing same cascade_id replaces old data."""
    conv_id1 = indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    # Modify trajectory
    sample_trajectory.steps.append(StepInfo(index=3, variant_field=20, content_text="extra"))
    conv_id2 = indexer.index_trajectory(sample_trajectory, cascade_id="c1")

    # Old conversation should be replaced
    cur = indexer.conn.execute("SELECT COUNT(*) FROM conversations WHERE cascade_id = 'c1'")
    assert cur.fetchone()[0] == 1

    cur = indexer.conn.execute("SELECT step_count FROM conversations WHERE cascade_id = 'c1'")
    assert cur.fetchone()[0] == 4  # now 4 steps


# --- FTS5 tests ---


def test_fts5_rounds_search(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """FTS5 search on rounds finds inserted prompts."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT r.prompt FROM rounds_fts fts JOIN rounds r ON r.id = fts.rowid "
        "WHERE rounds_fts MATCH 'protobuf' ORDER BY rank"
    )
    rows = cur.fetchall()
    assert len(rows) >= 1
    assert "protobuf" in rows[0][0].lower()


def test_fts5_steps_search(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """FTS5 search on steps finds inserted content."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT s.content_text FROM steps_fts fts JOIN steps s ON s.id = fts.rowid "
        "WHERE steps_fts MATCH 'wire' ORDER BY rank"
    )
    rows = cur.fetchall()
    assert len(rows) >= 1
    assert "wire" in rows[0][0].lower()


def test_fts5_checkpoints_search(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """FTS5 search on checkpoints finds inserted summaries."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    cur = indexer.conn.execute(
        "SELECT c.user_intent FROM checkpoints_fts fts JOIN checkpoints c ON c.id = fts.rowid "
        "WHERE checkpoints_fts MATCH 'protobuf' ORDER BY rank"
    )
    rows = cur.fetchall()
    assert len(rows) >= 1
    assert "protobuf" in rows[0][0].lower()


# --- is_indexed tests ---


def test_is_indexed_not_found(indexer: Indexer):
    """is_indexed returns False for unknown cascade_id."""
    assert not indexer.is_indexed("unknown", 0.0, 0)


def test_is_indexed_found(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """is_indexed returns True for matching mtime and size."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1", pb_mtime=1000.0, pb_size=5000)
    assert indexer.is_indexed("c1", 1000.0, 5000)


def test_is_indexed_stale_mtime(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """is_indexed returns False when mtime differs."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1", pb_mtime=1000.0, pb_size=5000)
    assert not indexer.is_indexed("c1", 2000.0, 5000)


def test_is_indexed_stale_size(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """is_indexed returns False when size differs."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1", pb_mtime=1000.0, pb_size=5000)
    assert not indexer.is_indexed("c1", 1000.0, 9999)


# --- get_status tests ---


def test_get_status_empty(indexer: Indexer):
    """get_status on empty database returns zeros."""
    status = indexer.get_status()
    assert status["conversation_count"] == 0
    assert status["step_count"] == 0
    assert status["round_count"] == 0
    assert status["checkpoint_count"] == 0


def test_get_status_after_indexing(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """get_status reflects indexed data."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    status = indexer.get_status()
    assert status["conversation_count"] == 1
    assert status["step_count"] == 3
    assert status["round_count"] == 1
    assert status["checkpoint_count"] == 1


# --- list_conversations tests ---


def test_list_conversations(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """list_conversations returns indexed conversations."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    sample_trajectory.cascade_id = "c2"
    indexer.index_trajectory(sample_trajectory, cascade_id="c2")

    convs = indexer.list_conversations()
    assert len(convs) == 2
    assert "cascade_id" in convs[0]
    assert "title" in convs[0]


def test_list_conversations_limit(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """list_conversations respects limit."""
    for i in range(5):
        indexer.index_trajectory(sample_trajectory, cascade_id=f"c{i}")
    convs = indexer.list_conversations(limit=3)
    assert len(convs) == 3


# --- get_conversation tests ---


def test_get_conversation(indexer: Indexer, sample_trajectory: TrajectoryInfo):
    """get_conversation returns full nested data."""
    indexer.index_trajectory(sample_trajectory, cascade_id="c1")
    conv = indexer.get_conversation("c1")
    assert conv is not None
    assert conv["cascade_id"] == "c1"
    assert len(conv["rounds"]) == 1
    assert len(conv["steps"]) == 3
    assert len(conv["checkpoints"]) == 1


def test_get_conversation_not_found(indexer: Indexer):
    """get_conversation returns None for unknown cascade_id."""
    assert indexer.get_conversation("nonexistent") is None


# --- Context manager tests ---


def test_context_manager(tmp_path: Path):
    """Indexer works as a context manager."""
    db_path = tmp_path / "ctx.db"
    with Indexer(db_path=db_path) as idx:
        idx.index_trajectory(
            TrajectoryInfo(cascade_id="c1", steps=[StepInfo(index=0)]),
            cascade_id="c1",
        )
    # DB should be accessible after context exit
    idx2 = Indexer(db_path=db_path)
    idx2.init_schema()
    convs = idx2.list_conversations()
    assert len(convs) == 1
    idx2.close()


# --- Real data tests ---


def test_index_real_file(real_pb_dir: Path | None, tmp_path: Path):
    """Index a real .pb file end-to-end."""
    if real_pb_dir is None:
        pytest.skip("No .pb files available")

    pb_files = sorted(real_pb_dir.glob("*.pb"))
    if not pb_files:
        pytest.skip("No .pb files available")

    idx = Indexer(db_path=tmp_path / "real.db")
    conv_id = idx.index_file(pb_files[0])
    assert conv_id is not None
    assert conv_id > 0

    status = idx.get_status()
    assert status["conversation_count"] == 1
    assert status["step_count"] > 0

    # Verify FTS5 works on real data
    conv = idx.get_conversation(pb_files[0].stem)
    assert conv is not None
    assert conv["step_count"] > 0
    idx.close()


def test_index_directory_incremental(real_pb_dir: Path | None, tmp_path: Path):
    """Index a directory, then re-run to verify incremental skip."""
    if real_pb_dir is None:
        pytest.skip("No .pb files available")

    idx = Indexer(db_path=tmp_path / "real.db")

    # First pass: index all
    ok1, skip1, fail1, errors1 = idx.index_directory(real_pb_dir, force=True)
    assert fail1 == 0, f"Errors: {errors1}"
    assert ok1 > 0

    # Second pass: should skip all (incremental)
    ok2, skip2, fail2, errors2 = idx.index_directory(real_pb_dir, force=False)
    assert ok2 == 0
    assert skip2 == ok1
    assert fail2 == 0
    idx.close()


# --- sync() tests ---


def _encrypt_pb(plaintext: bytes) -> bytes:
    """Encrypt plaintext into a valid .pb file (AES-256-GCM)."""
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def _make_trajectory_pb(
    cascade_id: str,
    prompt: str = "Hello world",
    response: str = "Hi there!",
    title: str = "Test Conversation",
) -> bytes:
    """Build a minimal valid protobuf trajectory and encrypt it as .pb."""
    from tests.test_parser import (
        encode_field_bytes,
        encode_field_string,
        encode_field_varint,
    )
    from dcr.parser import (
        VARIANT_CHECKPOINT,
        VARIANT_PLANNER_RESPONSE,
        VARIANT_USER_INPUT,
    )

    step1 = encode_field_varint(1, 0) + encode_field_varint(4, 1)
    step1 += encode_field_bytes(VARIANT_USER_INPUT, encode_field_string(1, prompt))

    step2 = encode_field_varint(1, 0) + encode_field_varint(4, 1)
    step2 += encode_field_bytes(VARIANT_PLANNER_RESPONSE, encode_field_string(8, response))

    cp = encode_field_string(4, f"{title}\nUser did something")
    step3 = encode_field_varint(1, 0) + encode_field_varint(4, 1)
    step3 += encode_field_bytes(VARIANT_CHECKPOINT, cp)

    traj = encode_field_string(1, f"traj-{cascade_id}")
    traj += encode_field_bytes(2, step1)
    traj += encode_field_bytes(2, step2)
    traj += encode_field_bytes(2, step3)
    traj += encode_field_string(6, cascade_id)
    traj += encode_field_varint(4, 1)
    traj += encode_field_varint(8, 2)

    return _encrypt_pb(traj)


@pytest.fixture
def fake_cascade_dir(tmp_path: Path) -> Path:
    """Create a temp cascade dir with 2 fake .pb files."""
    cascade_dir = tmp_path / "cascade"
    cascade_dir.mkdir()
    for cid, prompt, title in [
        ("conv-aaa", "How to parse protobuf?", "Protobuf Question"),
        ("conv-bbb", "Fix the database schema", "DB Schema Fix"),
    ]:
        pb_data = _make_trajectory_pb(cid, prompt=prompt, title=title)
        (cascade_dir / f"{cid}.pb").write_bytes(pb_data)
    return cascade_dir


def test_sync_new_files(indexer: Indexer, fake_cascade_dir: Path):
    """sync() indexes all new .pb files."""
    result = indexer.sync(fake_cascade_dir)
    assert result["new"] == 2
    assert result["updated"] == 0
    assert result["unchanged"] == 0
    assert result["archived"] == 0
    assert result["failed"] == 0
    status = indexer.get_status()
    assert status["conversation_count"] == 2


def test_sync_unchanged(indexer: Indexer, fake_cascade_dir: Path):
    """sync() skips unchanged files on second run."""
    indexer.sync(fake_cascade_dir)
    result = indexer.sync(fake_cascade_dir)
    assert result["new"] == 0
    assert result["updated"] == 0
    assert result["unchanged"] == 2
    assert result["archived"] == 0


def test_sync_detects_modified(indexer: Indexer, fake_cascade_dir: Path):
    """sync() re-indexes modified files (mtime change)."""
    indexer.sync(fake_cascade_dir)
    pb = fake_cascade_dir / "conv-aaa.pb"
    new_data = _make_trajectory_pb("conv-aaa", prompt="Updated prompt", title="Updated Title")
    pb.write_bytes(new_data)
    result = indexer.sync(fake_cascade_dir)
    assert result["updated"] == 1
    assert result["unchanged"] == 1
    conv = indexer.get_conversation("conv-aaa")
    assert conv["title"] == "Updated Title"


def test_sync_archives_stale(indexer: Indexer, fake_cascade_dir: Path):
    """sync() archives conversations whose .pb file was deleted (never deletes)."""
    indexer.sync(fake_cascade_dir)
    assert indexer.get_status()["conversation_count"] == 2
    (fake_cascade_dir / "conv-aaa.pb").unlink()
    result = indexer.sync(fake_cascade_dir)
    assert result["archived"] == 1
    assert result["unchanged"] == 1
    # Conversation is still in the database, marked as archived
    assert indexer.get_status()["conversation_count"] == 2
    assert indexer.get_status()["archived_count"] == 1
    assert indexer.get_status()["active_count"] == 1
    conv = indexer.get_conversation("conv-aaa")
    assert conv is not None
    assert conv["archived"] == 1
    assert conv["archived_at"] is not None
    assert indexer.get_conversation("conv-bbb") is not None


def test_sync_archives_stale_regardless_of_remove_stale_flag(indexer: Indexer, fake_cascade_dir: Path):
    """sync() always archives stale conversations, remove_stale flag is deprecated."""
    indexer.sync(fake_cascade_dir)
    (fake_cascade_dir / "conv-aaa.pb").unlink()
    # Even with remove_stale=False, conversations are archived (never deleted)
    result = indexer.sync(fake_cascade_dir, remove_stale=False)
    assert result["archived"] == 1
    assert indexer.get_status()["conversation_count"] == 2
    assert indexer.get_status()["archived_count"] == 1


def test_sync_detects_new_file(indexer: Indexer, fake_cascade_dir: Path):
    """sync() detects a new .pb file added between runs."""
    indexer.sync(fake_cascade_dir)
    pb_data = _make_trajectory_pb("conv-ccc", prompt="New question", title="New Chat")
    (fake_cascade_dir / "conv-ccc.pb").write_bytes(pb_data)
    result = indexer.sync(fake_cascade_dir)
    assert result["new"] == 1
    assert result["unchanged"] == 2
    assert indexer.get_status()["conversation_count"] == 3


def test_sync_default_dir(indexer: Indexer, tmp_path: Path, monkeypatch):
    """sync() with no args uses DEFAULT_CASCADE_DIR."""
    fake_dir = tmp_path / "fake_cascade"
    fake_dir.mkdir()
    pb_data = _make_trajectory_pb("conv-test")
    (fake_dir / "conv-test.pb").write_bytes(pb_data)

    import dcr.indexer as indexer_mod
    monkeypatch.setattr(indexer_mod, "DEFAULT_CASCADE_DIR", fake_dir)

    result = indexer.sync()
    assert result["new"] == 1
    assert indexer.get_status()["conversation_count"] == 1
    assert indexer.get_status()["archived_count"] == 0


def test_sync_real_data(real_pb_dir: Path | None, tmp_path: Path):
    """sync() works on real .pb files."""
    if real_pb_dir is None:
        pytest.skip("No .pb files available")

    idx = Indexer(db_path=tmp_path / "real.db")
    result = idx.sync(real_pb_dir)
    assert result["failed"] == 0, f"Errors: {result['errors']}"
    assert result["new"] > 0

    result2 = idx.sync(real_pb_dir)
    assert result2["new"] == 0
    assert result2["updated"] == 0
    assert result2["unchanged"] == result["new"]
    idx.close()


def test_archived_conversation_still_searchable(indexer: Indexer, fake_cascade_dir: Path):
    """An archived conversation remains in the database and is still searchable."""
    from dcr.search import SearchEngine

    indexer.sync(fake_cascade_dir)
    # Archive one conversation by removing its .pb file and syncing
    (fake_cascade_dir / "conv-aaa.pb").unlink()
    indexer.sync(fake_cascade_dir)

    # The archived conversation should still be findable via get_conversation
    conv = indexer.get_conversation("conv-aaa")
    assert conv is not None
    assert conv["archived"] == 1

    # The archived conversation should still appear in list_conversations
    convs = indexer.list_conversations(limit=100)
    archived_convs = [c for c in convs if c.get("archived")]
    assert len(archived_convs) == 1
    assert archived_convs[0]["cascade_id"] == "conv-aaa"

    # FTS5 search should still find content from the archived conversation
    cur = indexer.conn.execute(
        "SELECT r.prompt FROM rounds_fts fts JOIN rounds r ON r.id = fts.rowid "
        "WHERE rounds_fts MATCH 'protobuf' ORDER BY rank"
    )
    rows = cur.fetchall()
    assert len(rows) >= 1
    assert "protobuf" in rows[0][0].lower()

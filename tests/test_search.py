"""Tests for dcr.search module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from dcr.indexer import Indexer
from dcr.parser import (
    CheckpointInfo,
    RoundInfo,
    StepInfo,
    TrajectoryInfo,
)
from dcr.search import SearchEngine, SearchResult, SearchResults


# --- Fixtures ---


@pytest.fixture
def sample_trajectory() -> TrajectoryInfo:
    """Build a sample TrajectoryInfo with searchable content."""
    return TrajectoryInfo(
        trajectory_id="traj-001",
        cascade_id="cascade-001",
        trajectory_type=1,
        source=2,
        project_path="/home/user/projects/myapp",
        git_branch="main",
        model="glm-5-2",
        steps=[
            StepInfo(
                index=0,
                type=0,
                status=1,
                variant_field=19,
                content_text="How do I parse protobuf in Python?",
            ),
            StepInfo(
                index=1,
                type=0,
                status=1,
                variant_field=20,
                content_text="You can use the protobuf library for wire format parsing.",
            ),
            StepInfo(
                index=2,
                type=0,
                status=1,
                variant_field=28,
                content_text="pip install protobuf",
            ),
        ],
        checkpoints=[
            CheckpointInfo(
                step_index=2,
                user_intent="Protobuf Parsing Guide\nUser wants to parse protobuf data",
                session_summary="Explained protobuf wire format and installation",
                conversation_title="",
            ),
        ],
        rounds=[
            RoundInfo(
                round_number=1,
                prompt="How do I parse protobuf in Python?",
                start_step=0,
                end_step=2,
            ),
        ],
    )


@pytest.fixture
def second_trajectory() -> TrajectoryInfo:
    """Build a second trajectory with different project."""
    return TrajectoryInfo(
        trajectory_id="traj-002",
        cascade_id="cascade-002",
        trajectory_type=1,
        source=2,
        project_path="/home/user/projects/otherapp",
        git_branch="dev",
        model="glm-5-2",
        steps=[
            StepInfo(
                index=0,
                type=0,
                status=1,
                variant_field=19,
                content_text="How to configure SQLite FTS5?",
            ),
            StepInfo(
                index=1,
                type=0,
                status=1,
                variant_field=20,
                content_text="SQLite FTS5 is configured via CREATE VIRTUAL TABLE.",
            ),
        ],
        rounds=[
            RoundInfo(
                round_number=1,
                prompt="How to configure SQLite FTS5?",
                start_step=0,
                end_step=1,
            ),
        ],
    )


@pytest.fixture
def search_engine(tmp_path: Path, sample_trajectory: TrajectoryInfo, second_trajectory: TrajectoryInfo) -> SearchEngine:
    """Create a search engine with indexed test data."""
    engine = SearchEngine(db_path=tmp_path / "test.db", auto_sync=False)
    engine.indexer.init_schema()
    engine.indexer.index_trajectory(sample_trajectory, cascade_id="cascade-001")
    engine.indexer.index_trajectory(second_trajectory, cascade_id="cascade-002")
    yield engine
    engine.close()


@pytest.fixture
def real_pb_dir() -> Path | None:
    """Return the cascade directory if .pb files exist."""
    cascade_dir = Path.home() / ".codeium/windsurf/cascade"
    if cascade_dir.exists() and list(cascade_dir.glob("*.pb")):
        return cascade_dir
    return None


# --- Basic search tests ---


def test_search_returns_results(search_engine: SearchEngine):
    """Search returns results for a matching query."""
    results = search_engine.search("protobuf")
    assert results.total > 0
    assert len(results.results) > 0
    assert all(isinstance(r, SearchResult) for r in results.results)


def test_search_no_match(search_engine: SearchEngine):
    """Search returns empty for non-matching query."""
    results = search_engine.search("xyzzynonexistent")
    assert results.total == 0
    assert len(results.results) == 0


def test_search_empty_query(search_engine: SearchEngine):
    """Empty query returns empty results."""
    results = search_engine.search("")
    assert results.total == 0


def test_search_results_have_metadata(search_engine: SearchEngine):
    """Results include conversation metadata."""
    results = search_engine.search("protobuf")
    r = results.results[0]
    assert r.cascade_id
    assert r.title
    assert r.project_path
    assert r.source_table in ("rounds", "steps", "checkpoints")
    assert r.snippet
    assert r.score != 0


def test_search_snippet_contains_markers(search_engine: SearchEngine):
    """Snippets contain >>> and <<< markers around matches."""
    results = search_engine.search("protobuf")
    # At least one result should have markers
    has_markers = any(">>>" in r.snippet and "<<<" in r.snippet for r in results.results)
    assert has_markers


# --- Filter tests ---


def test_search_filter_project(search_engine: SearchEngine):
    """Project filter restricts results to matching project."""
    results = search_engine.search("protobuf", project="/home/user/projects/myapp")
    assert results.total > 0
    assert all(r.project_path == "/home/user/projects/myapp" for r in results.results)


def test_search_filter_project_prefix(search_engine: SearchEngine):
    """Project filter supports prefix matching."""
    results = search_engine.search("protobuf", project="/home/user/projects")
    assert results.total > 0
    assert all("/home/user/projects" in r.project_path for r in results.results)


def test_search_filter_project_no_match(search_engine: SearchEngine):
    """Project filter with no matching project returns empty."""
    results = search_engine.search("protobuf", project="/nonexistent")
    assert results.total == 0


def test_search_filter_date_from(search_engine: SearchEngine, sample_trajectory: TrajectoryInfo):
    """Date filter (from) restricts by created_at."""
    # Set created_at by adding a step with timestamp
    future = 2000000000.0
    results = search_engine.search("protobuf", date_from=future)
    assert results.total == 0


def test_search_filter_date_to(search_engine: SearchEngine):
    """Date filter (to) restricts by created_at."""
    results = search_engine.search("protobuf", date_to=1.0)
    assert results.total == 0


# --- Source table filter tests ---


def test_search_source_rounds(search_engine: SearchEngine):
    """Restrict search to rounds table."""
    results = search_engine.search("protobuf", source_table="rounds")
    assert all(r.source_table == "rounds" for r in results.results)


def test_search_source_steps(search_engine: SearchEngine):
    """Restrict search to steps table."""
    results = search_engine.search("protobuf", source_table="steps")
    assert all(r.source_table == "steps" for r in results.results)


def test_search_source_checkpoints(search_engine: SearchEngine):
    """Restrict search to checkpoints table."""
    results = search_engine.search("protobuf", source_table="checkpoints")
    assert all(r.source_table == "checkpoints" for r in results.results)


# --- search_conversations tests ---


def test_search_conversations_dedup(search_engine: SearchEngine):
    """search_conversations returns one result per conversation."""
    convs = search_engine.search_conversations("protobuf")
    ids = [c["conversation_id"] for c in convs]
    assert len(ids) == len(set(ids))


def test_search_conversations_limit(search_engine: SearchEngine):
    """search_conversations respects limit."""
    convs = search_engine.search_conversations("protobuf", limit=1)
    assert len(convs) <= 1


def test_search_conversations_has_snippet(search_engine: SearchEngine):
    """search_conversations includes best snippet."""
    convs = search_engine.search_conversations("protobuf")
    assert len(convs) > 0
    assert convs[0]["best_snippet"]


# --- Auto-sync tests ---


def test_auto_sync_enabled(tmp_path: Path, monkeypatch):
    """Auto-sync calls sync() before search."""
    engine = SearchEngine(db_path=tmp_path / "test.db", auto_sync=True)

    # Create a fake cascade dir with a .pb file
    from tests.test_indexer import _make_trajectory_pb

    fake_dir = tmp_path / "cascade"
    fake_dir.mkdir()
    pb_data = _make_trajectory_pb("sync-test", prompt="auto sync test query")
    (fake_dir / "sync-test.pb").write_bytes(pb_data)

    import dcr.indexer as indexer_mod
    monkeypatch.setattr(indexer_mod, "DEFAULT_CASCADE_DIR", fake_dir)
    # Disable Devin Local sync (no real sessions.db in test env).
    monkeypatch.setattr("dcr.devin_local.DEFAULT_DEVIN_LOCAL_DB", Path("/nonexistent/dl.db"))

    results = engine.search("auto sync")
    assert results.sync_info is not None
    assert results.sync_info["new"] >= 1
    assert results.total > 0
    engine.close()


def test_auto_sync_disabled(tmp_path: Path):
    """Auto-sync disabled returns None sync_info."""
    engine = SearchEngine(db_path=tmp_path / "test.db", auto_sync=False)
    results = engine.search("anything")
    assert results.sync_info is None
    engine.close()


# --- Context manager tests ---


def test_context_manager(tmp_path: Path, sample_trajectory: TrajectoryInfo):
    """SearchEngine works as context manager."""
    with SearchEngine(db_path=tmp_path / "test.db", auto_sync=False) as engine:
        engine.indexer.init_schema()
        engine.indexer.index_trajectory(sample_trajectory, cascade_id="c1")
        results = engine.search("protobuf")
        assert results.total > 0


# --- FTS5 query escaping tests ---


def test_escape_fts_query_simple():
    """Simple query is tokenized and quoted."""
    escaped = SearchEngine._escape_fts_query("hello world")
    assert '"hello"' in escaped
    assert '"world"' in escaped


def test_escape_fts_query_with_operators():
    """Operators are preserved."""
    escaped = SearchEngine._escape_fts_query("protobuf AND python")
    assert "AND" in escaped


def test_escape_fts_query_empty():
    """Empty query returns empty string."""
    assert SearchEngine._escape_fts_query("") == ""
    assert SearchEngine._escape_fts_query("   ") == ""


# --- Real data tests ---


def test_search_real_data(real_pb_dir: Path | None, tmp_path: Path):
    """Search works on real indexed data."""
    if real_pb_dir is None:
        pytest.skip("No .pb files available")

    engine = SearchEngine(db_path=tmp_path / "real.db", auto_sync=False)
    engine.indexer.index_directory(real_pb_dir, force=True)

    # Search for a common term
    results = engine.search("the")
    assert results.total > 0
    assert len(results.results) > 0

    # Search with project filter
    convs = engine.list_conversations() if hasattr(engine, "list_conversations") else []
    if engine.indexer.list_conversations():
        first = engine.indexer.list_conversations(limit=1)[0]
        if first["project_path"]:
            project_results = engine.search("the", project=first["project_path"])
            assert all(r.project_path == first["project_path"] for r in project_results.results)

    engine.close()


def test_search_real_data_conversations(real_pb_dir: Path | None, tmp_path: Path):
    """search_conversations works on real data."""
    if real_pb_dir is None:
        pytest.skip("No .pb files available")

    engine = SearchEngine(db_path=tmp_path / "real.db", auto_sync=False)
    engine.indexer.index_directory(real_pb_dir, force=True)

    convs = engine.search_conversations("error", limit=5)
    assert len(convs) <= 5
    for c in convs:
        assert "cascade_id" in c
        assert "title" in c
        assert "best_snippet" in c


# --- Phase 2: source_type filter + tool_calls search ---


def test_search_filter_source_type(search_engine: SearchEngine, sample_trajectory: TrajectoryInfo):
    """search with source_type filter restricts results to that source."""
    # sample_trajectory is indexed as cascade (default source_type)
    results = search_engine.search("parse", source_type="cascade")
    assert results.total > 0
    # No devin_local conversations in this test DB → should return 0
    results = search_engine.search("parse", source_type="devin_local")
    assert results.total == 0


def test_search_source_table_tool_calls(search_engine: SearchEngine, sample_trajectory: TrajectoryInfo):
    """search with source_table=tool_calls searches the tool_calls FTS table."""
    # sample_trajectory has no tool_calls, so this should return 0 without error
    results = search_engine.search("anything", source_table="tool_calls")
    assert results.total == 0

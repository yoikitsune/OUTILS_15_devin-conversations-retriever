"""Tests for dcr.cli module."""

from __future__ import annotations

from pathlib import Path

import pytest

from dcr.cli import main
from dcr.indexer import Indexer
from dcr.parser import (
    CheckpointInfo,
    RoundInfo,
    StepInfo,
    TrajectoryInfo,
)


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
        ],
        checkpoints=[
            CheckpointInfo(
                step_index=1,
                user_intent="Protobuf Parsing Guide\nUser wants to parse protobuf data",
                session_summary="Explained protobuf wire format",
                conversation_title="",
            ),
        ],
        rounds=[
            RoundInfo(
                round_number=1,
                prompt="How do I parse protobuf in Python?",
                start_step=0,
                end_step=1,
            ),
        ],
    )


@pytest.fixture
def db_path(tmp_path: Path, sample_trajectory: TrajectoryInfo) -> Path:
    """Create a test database with indexed data."""
    db = tmp_path / "test.db"
    idx = Indexer(db_path=db)
    idx.init_schema()
    idx.index_trajectory(sample_trajectory, cascade_id="cascade-001")
    idx.close()
    return db


@pytest.fixture
def real_db(tmp_path: Path) -> Path | None:
    """Create a DB from real .pb files if available."""
    cascade_dir = Path.home() / ".codeium/windsurf/cascade"
    if not cascade_dir.exists() or not list(cascade_dir.glob("*.pb")):
        return None
    db = tmp_path / "real.db"
    idx = Indexer(db_path=db)
    idx.index_directory(cascade_dir, force=True)
    idx.close()
    return db


# --- Tests ---


def test_cli_no_command(capsys: pytest.CaptureFixture[str]):
    """Running dcr with no command prints help."""
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Available commands" in out or "usage" in out.lower()


def test_cli_status(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """status command shows database stats."""
    ret = main(["--db", str(db_path), "status"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Conversations:" in out
    assert "Steps:" in out


def test_cli_list(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """list command shows conversations."""
    ret = main(["--db", str(db_path), "list", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Protobuf" in out
    assert "myapp" in out


def test_cli_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """list on empty database shows message."""
    db = tmp_path / "empty.db"
    ret = main(["--db", str(db), "list", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "No conversations" in out


def test_cli_search(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """search command returns results."""
    ret = main(["--db", str(db_path), "search", "protobuf", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Found" in out
    assert "protobuf" in out.lower() or "Protobuf" in out


def test_cli_search_no_results(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """search with no matches returns appropriate message."""
    ret = main(["--db", str(db_path), "search", "xyzzynonexistent", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "No results" in out


def test_cli_search_with_project_filter(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """search with project filter."""
    ret = main(["--db", str(db_path), "search", "protobuf", "-p", "/home/user/projects/myapp", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Found" in out


def test_cli_search_source_filter(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """search with source table filter."""
    ret = main(["--db", str(db_path), "search", "protobuf", "-s", "steps", "--no-sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "[steps]" in out


def test_cli_show(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """show command displays conversation details."""
    ret = main(["--db", str(db_path), "show", "cascade-001"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Conversation:" in out
    assert "cascade-001" in out
    assert "Project:" in out
    assert "Rounds:" in out
    assert "Steps:" in out


def test_cli_show_not_found(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """show with unknown ID returns error."""
    ret = main(["--db", str(db_path), "show", "nonexistent-id"])
    assert ret == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_cli_show_prefix(db_path: Path, capsys: pytest.CaptureFixture[str]):
    """show with cascade_id prefix resolves to full ID."""
    ret = main(["--db", str(db_path), "show", "cascade"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "cascade-001" in out


def test_cli_html(db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """html command generates HTML file."""
    out_file = tmp_path / "overview.html"
    ret = main(["--db", str(db_path), "html", "-o", str(out_file), "--no-sync"])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<html" in content
    assert "Protobuf" in content
    assert "myapp" in content


def test_cli_sync(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch):
    """sync command syncs database."""
    from tests.test_indexer import _make_trajectory_pb

    fake_dir = tmp_path / "cascade"
    fake_dir.mkdir()
    pb_data = _make_trajectory_pb("sync-cli-test", prompt="cli sync test")
    (fake_dir / "sync-cli-test.pb").write_bytes(pb_data)

    db = tmp_path / "sync.db"
    import dcr.indexer as indexer_mod
    monkeypatch.setattr(indexer_mod, "DEFAULT_CASCADE_DIR", fake_dir)

    ret = main(["--db", str(db), "sync"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "New:" in out
    assert "1" in out


# --- Real data tests ---


def test_cli_status_real(real_db: Path | None, capsys: pytest.CaptureFixture[str]):
    """status on real database."""
    if real_db is None:
        pytest.skip("No .pb files available")
    ret = main(["--db", str(real_db), "status"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Conversations:" in out
    # Should have a positive count
    assert any(c.isdigit() and int(c) > 0 for c in out.split())


def test_cli_list_real(real_db: Path | None, capsys: pytest.CaptureFixture[str]):
    """list on real database."""
    if real_db is None:
        pytest.skip("No .pb files available")
    ret = main(["--db", str(real_db), "list", "--no-sync", "-l", "5"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Total:" in out


def test_cli_search_real(real_db: Path | None, capsys: pytest.CaptureFixture[str]):
    """search on real database."""
    if real_db is None:
        pytest.skip("No .pb files available")
    ret = main(["--db", str(real_db), "search", "the", "--no-sync", "-l", "5"])
    assert ret == 0
    out = capsys.readouterr().out
    # Should find results in real data
    assert "Found" in out


def test_cli_html_real(real_db: Path | None, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """html on real database."""
    if real_db is None:
        pytest.skip("No .pb files available")
    out_file = tmp_path / "real_overview.html"
    ret = main(["--db", str(real_db), "html", "-o", str(out_file), "--no-sync"])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Conversations Overview" in content

"""Tests for dcr.parser module."""

from __future__ import annotations

from pathlib import Path

import pytest

from dcr.parser import (
    VARIANT_CHECKPOINT,
    VARIANT_PLANNER_RESPONSE,
    VARIANT_USER_INPUT,
    CheckpointInfo,
    RoundInfo,
    StepInfo,
    TrajectoryInfo,
    extract_step_text,
    group_rounds,
    iter_fields,
    parse,
    parse_checkpoint,
    parse_file,
    parse_step,
    parse_tag,
    parse_trajectory_metadata,
    read_varint,
)


# --- Protobuf encoding helpers (for building synthetic test data) ---


def encode_varint(val: int) -> bytes:
    """Encode an integer as a protobuf varint."""
    buf: list[int] = []
    while val > 0x7F:
        buf.append((val & 0x7F) | 0x80)
        val >>= 7
    buf.append(val & 0x7F)
    return bytes(buf)


def encode_field_varint(field_no: int, value: int) -> bytes:
    """Encode a varint field."""
    tag = (field_no << 3) | 0
    return encode_varint(tag) + encode_varint(value)


def encode_field_bytes(field_no: int, data: bytes) -> bytes:
    """Encode a length-delimited field."""
    tag = (field_no << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data


def encode_field_string(field_no: int, text: str) -> bytes:
    """Encode a string field."""
    return encode_field_bytes(field_no, text.encode("utf-8"))


# --- Fixtures ---


@pytest.fixture
def synthetic_trajectory_bytes() -> bytes:
    """Build a minimal CortexTrajectory with 3 steps:
    1. user_input (variant 19) with prompt text
    2. planner_response (variant 20) with visible response
    3. checkpoint (variant 30) with summary fields
    """
    # Step 1: user_input
    user_input_variant = encode_field_string(1, "Hello, how are you?")
    step1 = encode_field_varint(1, 0)  # type=0
    step1 += encode_field_varint(4, 1)  # status=1
    step1 += encode_field_bytes(VARIANT_USER_INPUT, user_input_variant)

    # Step 2: planner_response
    planner_variant = encode_field_string(8, "I am fine, thank you!")
    step2 = encode_field_varint(1, 0)
    step2 += encode_field_varint(4, 1)
    step2 += encode_field_bytes(VARIANT_PLANNER_RESPONSE, planner_variant)

    # Step 3: checkpoint
    cp_variant = encode_field_varint(1, 0)  # checkpoint_index=0
    cp_variant += encode_field_string(4, "User greeted the assistant")
    cp_variant += encode_field_string(5, "Short greeting exchange")
    cp_variant += encode_field_string(10, "Greeting Conversation")
    step3 = encode_field_varint(1, 0)
    step3 += encode_field_varint(4, 1)
    step3 += encode_field_bytes(VARIANT_CHECKPOINT, cp_variant)

    # Top-level trajectory
    traj = encode_field_string(1, "traj-uuid-123")  # trajectory_id
    traj += encode_field_bytes(2, step1)  # step
    traj += encode_field_bytes(2, step2)  # step
    traj += encode_field_bytes(2, step3)  # step
    traj += encode_field_string(6, "cascade-uuid-456")  # cascade_id
    traj += encode_field_varint(4, 1)  # trajectory_type=1
    traj += encode_field_varint(8, 2)  # source=2

    return traj


@pytest.fixture
def real_bin_path() -> Path | None:
    """Return path to a real decrypted .bin file if available."""
    p = Path("artifacts/decrypted/155522f6.bin")
    if p.exists():
        return p
    # Try decrypting one
    cascade_dir = Path.home() / ".codeium/windsurf/cascade"
    pb_files = sorted(cascade_dir.glob("*.pb"))
    if not pb_files:
        return None
    from dcr.decrypt import decrypt_file

    out = Path("artifacts/decrypted") / (pb_files[0].stem + ".bin")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(decrypt_file(pb_files[0]))
    return out


# --- Low-level utility tests ---


def test_read_varint_simple():
    """Single-byte varint."""
    val, pos = read_varint(b"\x05", 0)
    assert val == 5
    assert pos == 1


def test_read_varint_multi_byte():
    """Multi-byte varint (300 = 0xAC 0x02)."""
    val, pos = read_varint(b"\xAC\x02", 0)
    assert val == 300
    assert pos == 2


def test_read_varint_unterminated():
    """Unterminated varint raises ValueError."""
    with pytest.raises(ValueError, match="unterminated"):
        read_varint(b"\x80", 0)


def test_parse_tag():
    """Tag parsing: field 3, wire type 2."""
    fno, wt = parse_tag((3 << 3) | 2)
    assert fno == 3
    assert wt == 2


def test_iter_fields_basic():
    """iter_fields yields correct field numbers and values."""
    msg = encode_field_varint(1, 42) + encode_field_string(3, "hello")
    fields = list(iter_fields(msg))
    assert len(fields) == 2
    assert fields[0][0] == 1  # field_no
    assert fields[0][1] == 0  # wire_type (varint)
    assert fields[0][3] == 42  # value
    assert fields[1][0] == 3
    assert fields[1][1] == 2  # wire_type (length-delimited)
    assert fields[1][3] == b"hello"


# --- parse_trajectory_metadata tests ---


def test_parse_trajectory_metadata_synthetic(synthetic_trajectory_bytes: bytes):
    """Parse synthetic trajectory metadata."""
    meta = parse_trajectory_metadata(synthetic_trajectory_bytes)
    assert meta["trajectory_id"] == "traj-uuid-123"
    assert meta["cascade_id"] == "cascade-uuid-456"
    assert meta["trajectory_type"] == 1
    assert meta["source"] == 2
    assert len(meta["steps"]) == 3


def test_parse_trajectory_metadata_empty():
    """Empty buffer produces empty metadata."""
    meta = parse_trajectory_metadata(b"")
    assert meta["trajectory_id"] == ""
    assert meta["steps"] == []


# --- parse_step tests ---


def test_parse_step_user_input():
    """Parse a user_input step."""
    variant = encode_field_string(1, "What is 2+2?")
    step_buf = encode_field_varint(1, 5) + encode_field_bytes(VARIANT_USER_INPUT, variant)
    step = parse_step(step_buf, 0)
    assert step.type == 5
    assert step.variant_field == VARIANT_USER_INPUT
    assert step.content_text == "What is 2+2?"


def test_parse_step_planner_response():
    """Parse a planner_response step, extracting field 8."""
    variant = encode_field_string(3, "thinking...") + encode_field_string(8, "The answer is 4.")
    step_buf = encode_field_varint(1, 5) + encode_field_bytes(VARIANT_PLANNER_RESPONSE, variant)
    step = parse_step(step_buf, 2)
    assert step.variant_field == VARIANT_PLANNER_RESPONSE
    assert step.content_text == "The answer is 4."


def test_parse_step_no_variant():
    """Step with no variant field produces empty text."""
    step_buf = encode_field_varint(1, 0) + encode_field_varint(4, 1)
    step = parse_step(step_buf, 0)
    assert step.variant_field is None
    assert step.content_text == ""


# --- parse_checkpoint tests ---


def test_parse_checkpoint_basic():
    """Parse a checkpoint with summary fields."""
    cp_buf = (
        encode_field_varint(1, 0)
        + encode_field_string(4, "User asked a question")
        + encode_field_string(5, "Q&A about math")
        + encode_field_string(10, "Math Question")
    )
    cp = parse_checkpoint(cp_buf, 5)
    assert cp.step_index == 5
    assert cp.checkpoint_index == 0
    assert cp.user_intent == "User asked a question"
    assert cp.session_summary == "Q&A about math"
    assert cp.conversation_title == "Math Question"


def test_parse_checkpoint_with_edited_files():
    """Parse checkpoint with edited_file_map entries."""
    file_entry = encode_field_string(1, "/path/to/file.py")
    cp_buf = encode_field_bytes(7, file_entry) + encode_field_bytes(7, encode_field_string(1, "/other/file.ts"))
    cp = parse_checkpoint(cp_buf, 0)
    assert "/path/to/file.py" in cp.edited_files
    assert "/other/file.ts" in cp.edited_files


def test_parse_checkpoint_empty():
    """Empty checkpoint buffer produces default values."""
    cp = parse_checkpoint(b"", 0)
    assert cp.step_index == 0
    assert cp.user_intent == ""
    assert cp.edited_files == []


# --- extract_step_text tests ---


def test_extract_step_text_empty():
    """Empty variant data returns empty string."""
    assert extract_step_text(VARIANT_USER_INPUT, b"") == ""


def test_extract_step_text_unknown_variant():
    """Unknown variant extracts available strings."""
    variant = encode_field_string(1, "some text")
    result = extract_step_text(99, variant)
    assert "some text" in result


# --- group_rounds tests ---


def test_group_rounds_two_rounds():
    """Two user_input steps produce two rounds."""
    steps = [
        StepInfo(index=0, variant_field=VARIANT_USER_INPUT, content_text="First question"),
        StepInfo(index=1, variant_field=VARIANT_PLANNER_RESPONSE, content_text="First answer"),
        StepInfo(index=2, variant_field=VARIANT_USER_INPUT, content_text="Second question"),
        StepInfo(index=3, variant_field=VARIANT_PLANNER_RESPONSE, content_text="Second answer"),
    ]
    rounds = group_rounds(steps)
    assert len(rounds) == 2
    assert rounds[0].round_number == 1
    assert rounds[0].prompt == "First question"
    assert rounds[0].start_step == 0
    assert rounds[0].end_step == 1
    assert rounds[1].round_number == 2
    assert rounds[1].prompt == "Second question"
    assert rounds[1].start_step == 2
    assert rounds[1].end_step == 3


def test_group_rounds_no_user_input():
    """No user_input steps means no rounds."""
    steps = [
        StepInfo(index=0, variant_field=VARIANT_PLANNER_RESPONSE, content_text="response"),
    ]
    rounds = group_rounds(steps)
    assert rounds == []


def test_group_rounds_empty():
    """Empty steps list produces empty rounds."""
    assert group_rounds([]) == []


# --- parse (full) tests ---


def test_parse_synthetic(synthetic_trajectory_bytes: bytes):
    """Parse a full synthetic trajectory."""
    traj = parse(synthetic_trajectory_bytes)
    assert traj.trajectory_id == "traj-uuid-123"
    assert traj.cascade_id == "cascade-uuid-456"
    assert traj.trajectory_type == 1
    assert traj.source == 2
    assert traj.step_count == 3
    assert traj.round_count == 1

    # Step 0: user_input
    assert traj.steps[0].variant_field == VARIANT_USER_INPUT
    assert traj.steps[0].content_text == "Hello, how are you?"

    # Step 1: planner_response
    assert traj.steps[1].variant_field == VARIANT_PLANNER_RESPONSE
    assert traj.steps[1].content_text == "I am fine, thank you!"

    # Step 2: checkpoint
    assert traj.steps[2].variant_field == VARIANT_CHECKPOINT
    assert len(traj.checkpoints) == 1
    assert traj.checkpoints[0].user_intent == "User greeted the assistant"
    assert traj.checkpoints[0].conversation_title == "Greeting Conversation"

    # Title from checkpoint
    assert traj.title == "Greeting Conversation"


def test_parse_empty():
    """Parsing empty bytes returns empty TrajectoryInfo."""
    traj = parse(b"")
    assert traj.trajectory_id == ""
    assert traj.step_count == 0
    assert traj.round_count == 0


def test_parse_title_fallback():
    """Title falls back to cascade_id when no checkpoint title exists."""
    traj = TrajectoryInfo(cascade_id="abc-123")
    assert traj.title == "abc-123"


# --- Real data test ---


def test_parse_real_file(real_bin_path: Path | None):
    """Parse a real decrypted .bin file and check basic structure."""
    if real_bin_path is None:
        pytest.skip("No .pb files available for testing")

    traj = parse_file(real_bin_path)
    assert traj.step_count > 0
    assert traj.trajectory_id  # non-empty
    # Real trajectories should have at least one round
    assert traj.round_count > 0
    # At least some steps should have content_text
    has_text = any(s.content_text for s in traj.steps)
    assert has_text, "No step has extractable text"


def test_parse_real_file_rounds_have_prompts(real_bin_path: Path | None):
    """Rounds from real data should have non-empty prompts."""
    if real_bin_path is None:
        pytest.skip("No .pb files available for testing")

    traj = parse_file(real_bin_path)
    if traj.rounds:
        first_round = traj.rounds[0]
        assert first_round.prompt  # non-empty
        assert first_round.start_step >= 0
        assert first_round.end_step >= first_round.start_step

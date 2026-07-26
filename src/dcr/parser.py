"""Protobuf wire-format parser for Windsurf Cascade CortexTrajectory.

Adapted from dayearleo/windsurf-local-user-data-decryption (MIT).
See ADR-0003 for reuse rationale.

Parses decrypted .pb plaintext into structured conversation data
without requiring compiled protobuf schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# --- Known variant field numbers ---

VARIANT_USER_INPUT = 19
VARIANT_PLANNER_RESPONSE = 20
VARIANT_RUN_COMMAND = 28
VARIANT_CHECKPOINT = 30
VARIANT_COMMAND_RESULT = 37


# --- Low-level wire-format utilities ---


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    """Read a varint from buf at pos.

    Args:
        buf: Byte buffer.
        pos: Starting position.

    Returns:
        Tuple of (value, new_position).

    Raises:
        ValueError: If varint is unterminated.
    """
    val = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7
    raise ValueError("unterminated varint")


def parse_tag(tag: int) -> tuple[int, int]:
    """Decode a protobuf tag into (field_number, wire_type)."""
    return tag >> 3, tag & 7


def skip_value(buf: bytes, pos: int, wire_type: int) -> int:
    """Skip a single field value. Return new position."""
    if wire_type == 0:
        _, pos = read_varint(buf, pos)
    elif wire_type == 1:
        pos += 8
    elif wire_type == 2:
        length, pos = read_varint(buf, pos)
        pos += length
    elif wire_type == 5:
        pos += 4
    elif wire_type == 3:
        while True:
            t, pos = read_varint(buf, pos)
            _, wt = parse_tag(t)
            if wt == 4:
                return pos
            pos = skip_value(buf, pos, wt)
    else:
        raise ValueError(f"unknown wire type {wire_type}")
    return pos


def iter_fields(
    buf: bytes, start: int = 0, end: int | None = None
) -> Iterator[tuple[int, int, int, bytes | int]]:
    """Iterate over protobuf fields in a message buffer.

    Args:
        buf: Byte buffer containing a protobuf message.
        start: Starting offset (default 0).
        end: Ending offset (default len(buf)).

    Yields:
        Tuples of (field_no, wire_type, value_offset, value).
        For varint (wt=0): value is int.
        For 64-bit (wt=1): value is bytes (8 bytes).
        For length-delimited (wt=2): value is bytes (the payload).
        For 32-bit (wt=5): value is bytes (4 bytes).
    """
    if end is None:
        end = len(buf)
    pos = start
    while pos < end:
        tag, pos = read_varint(buf, pos)
        fno, wt = parse_tag(tag)
        if wt == 0:
            val, new_pos = read_varint(buf, pos)
            yield fno, wt, pos, val
            pos = new_pos
        elif wt == 1:
            yield fno, wt, pos, buf[pos : pos + 8]
            pos += 8
        elif wt == 2:
            length, lpos = read_varint(buf, pos)
            yield fno, wt, lpos, buf[lpos : lpos + length]
            pos = lpos + length
        elif wt == 5:
            yield fno, wt, pos, buf[pos : pos + 4]
            pos += 4
        else:
            raise ValueError(f"wire type {wt} unsupported at {pos}")


# --- Data classes ---


@dataclass
class StepInfo:
    """A single step in a trajectory."""

    index: int
    type: int | None = None
    status: int | None = None
    variant_field: int | None = None
    variant_data: bytes = b""
    content_text: str = ""
    timestamp: float | None = None
    model: str = ""


@dataclass
class CheckpointInfo:
    """A checkpoint summary within a trajectory."""

    step_index: int
    checkpoint_index: int | None = None
    user_intent: str = ""
    session_summary: str = ""
    code_change_summary: str = ""
    memory_summary: str = ""
    conversation_title: str = ""
    plan_snapshot: str = ""
    intent_only: bool = False
    included_step_index_start: int | None = None
    included_step_index_end: int | None = None
    included_step_indices: list[int] = field(default_factory=list)
    edited_files: list[str] = field(default_factory=list)


@dataclass
class RoundInfo:
    """A conversation round (user prompt + AI response cycle)."""

    round_number: int
    prompt: str
    start_step: int
    end_step: int


@dataclass
class TrajectoryInfo:
    """Parsed CortexTrajectory."""

    trajectory_id: str = ""
    cascade_id: str = ""
    trajectory_type: int | None = None
    source: int | None = None
    project_path: str = ""
    git_branch: str = ""
    model: str = ""
    steps: list[StepInfo] = field(default_factory=list)
    checkpoints: list[CheckpointInfo] = field(default_factory=list)
    rounds: list[RoundInfo] = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def created_at(self) -> float | None:
        """Timestamp of the first step (Unix epoch seconds)."""
        for s in self.steps:
            if s.timestamp is not None:
                return s.timestamp
        return None

    @property
    def updated_at(self) -> float | None:
        """Timestamp of the last step (Unix epoch seconds)."""
        for s in reversed(self.steps):
            if s.timestamp is not None:
                return s.timestamp
        return None

    @property
    def title(self) -> str:
        """Best available title for this conversation.

        Priority:
        1. conversation_title from any checkpoint (field 10)
        2. First line of user_intent from the first checkpoint
        3. First user prompt (truncated to 80 chars)
        4. cascade_id or trajectory_id
        """
        # 1. conversation_title from checkpoints
        for cp in self.checkpoints:
            if cp.conversation_title:
                return cp.conversation_title

        # 2. First line of user_intent from the first checkpoint
        if self.checkpoints:
            first_cp = self.checkpoints[0]
            if first_cp.user_intent:
                first_line = first_cp.user_intent.split("\n")[0].strip()
                if first_line:
                    return first_line

        # 3. First user prompt truncated
        for s in self.steps:
            if s.variant_field == VARIANT_USER_INPUT and s.content_text:
                text = s.content_text.strip().split("\n")[0]
                return text[:80] + ("..." if len(text) > 80 else "")

        # 4. Fallback
        return self.cascade_id or self.trajectory_id


# --- Text extraction ---


def _extract_strings(buf: bytes, min_len: int = 2) -> list[str]:
    """Extract all UTF-8 string fields from a protobuf message.

    Recurses into sub-messages to find nested strings.
    """
    strings: list[str] = []
    for _fno, wt, _off, val in iter_fields(buf):
        if wt == 2 and isinstance(val, bytes) and len(val) >= min_len:
            try:
                text = val.decode("utf-8")
                if all(c.isprintable() or c in "\n\r\t" for c in text):
                    strings.append(text)
            except UnicodeDecodeError:
                pass
            # Try recursing into sub-messages
            try:
                strings.extend(_extract_strings(val, min_len))
            except (ValueError, IndexError):
                pass
    return strings


def extract_step_text(variant_field: int, variant_data: bytes) -> str:
    """Extract human-readable text from a step's variant data.

    For known variants, extracts specific fields.
    For unknown variants, extracts all string-like fields.

    Args:
        variant_field: The protobuf field number of the variant.
        variant_data: Raw bytes of the variant message.

    Returns:
        Extracted text string (may be empty).
    """
    if not variant_data:
        return ""

    if variant_field == VARIANT_PLANNER_RESPONSE:
        # Field 8 = visible response text
        for fno, wt, _off, val in iter_fields(variant_data):
            if fno == 8 and wt == 2 and isinstance(val, bytes):
                return val.decode("utf-8", errors="replace")
        # Fallback: first string found
        strings = _extract_strings(variant_data)
        return strings[0] if strings else ""

    elif variant_field == VARIANT_USER_INPUT:
        # Field 1 = user prompt text
        for fno, wt, _off, val in iter_fields(variant_data):
            if fno == 1 and wt == 2 and isinstance(val, bytes):
                try:
                    return val.decode("utf-8", errors="replace")
                except UnicodeDecodeError:
                    pass
        strings = _extract_strings(variant_data)
        return strings[0] if strings else ""

    elif variant_field == VARIANT_RUN_COMMAND:
        strings = _extract_strings(variant_data)
        return strings[0] if strings else ""

    elif variant_field == VARIANT_COMMAND_RESULT:
        strings = _extract_strings(variant_data)
        return strings[0] if strings else ""

    else:
        strings = _extract_strings(variant_data)
        return " | ".join(strings) if strings else ""


# --- Parsers ---


def parse_workspace_info(ws_buf: bytes) -> dict:
    """Parse top-level field 7 (workspace info).

    Structure: field 7 → {1: workspace_msg, 2: timestamp, 3: workspace_id}
    workspace_msg → {1: project_path, 2: project_path_dup, 3: repo_info, 4: git_branch}

    Returns:
        Dict with project_path, git_branch, workspace_id.
    """
    info: dict = {"project_path": "", "git_branch": "", "workspace_id": ""}
    for fno, wt, _off, val in iter_fields(ws_buf):
        if fno == 1 and wt == 2 and isinstance(val, bytes):
            # workspace_msg sub-message
            for sfno, swt, _, sval in iter_fields(val):
                if sfno == 1 and swt == 2 and isinstance(sval, bytes):
                    path = sval.decode("utf-8", errors="replace")
                    if path.startswith("file://"):
                        path = path[7:]
                    info["project_path"] = path
                elif sfno == 4 and swt == 2 and isinstance(sval, bytes):
                    info["git_branch"] = sval.decode("utf-8", errors="replace")
        elif fno == 3 and wt == 2 and isinstance(val, bytes):
            info["workspace_id"] = val.decode("utf-8", errors="replace")
    return info


def parse_trajectory_metadata(buf: bytes) -> dict:
    """Parse top-level CortexTrajectory metadata fields.

    Returns:
        Dict with trajectory_id, cascade_id, trajectory_type, source,
        project_path, git_branch, steps (raw bytes list).
    """
    info: dict = {
        "trajectory_id": "",
        "cascade_id": "",
        "trajectory_type": None,
        "source": None,
        "project_path": "",
        "git_branch": "",
        "steps": [],
    }
    for fno, wt, _off, val in iter_fields(buf):
        if fno == 1 and wt == 2 and isinstance(val, bytes):
            info["trajectory_id"] = val.decode("utf-8", errors="replace")
        elif fno == 6 and wt == 2 and isinstance(val, bytes):
            info["cascade_id"] = val.decode("utf-8", errors="replace")
        elif fno == 4 and wt == 0 and isinstance(val, int):
            info["trajectory_type"] = val
        elif fno == 8 and wt == 0 and isinstance(val, int):
            info["source"] = val
        elif fno == 2 and wt == 2 and isinstance(val, bytes):
            info["steps"].append(val)
        elif fno == 7 and wt == 2 and isinstance(val, bytes):
            ws = parse_workspace_info(val)
            info["project_path"] = ws["project_path"]
            info["git_branch"] = ws["git_branch"]
    return info


def parse_step_metadata(meta_buf: bytes) -> tuple[float | None, str]:
    """Parse step metadata (field 5) to extract timestamp and model.

    Args:
        meta_buf: Raw bytes of the metadata sub-message.

    Returns:
        Tuple of (timestamp_seconds, model_name).
    """
    timestamp: float | None = None
    model: str = ""

    for fno, wt, _off, val in iter_fields(meta_buf):
        if fno == 1 and wt == 2 and isinstance(val, bytes):
            # Sub-message: {1: seconds (varint), 2: nanos (varint)}
            for sfno, swt, _, sval in iter_fields(val):
                if sfno == 1 and swt == 0 and isinstance(sval, int) and sval > 0:
                    timestamp = float(sval)
        elif fno == 28 and wt == 2 and isinstance(val, bytes):
            model = val.decode("utf-8", errors="replace")

    return timestamp, model


def parse_step(step_buf: bytes, index: int) -> StepInfo:
    """Parse a CortexTrajectoryStep.

    Args:
        step_buf: Raw bytes of the step message.
        index: Step index within the trajectory.

    Returns:
        StepInfo with parsed fields and extracted text.
    """
    step = StepInfo(index=index)
    for fno, wt, _off, val in iter_fields(step_buf):
        if fno == 1 and wt == 0 and isinstance(val, int):
            step.type = val
        elif fno == 4 and wt == 0 and isinstance(val, int):
            step.status = val
        elif fno == 5 and wt == 2 and isinstance(val, bytes):
            step.timestamp, step.model = parse_step_metadata(val)
        elif 7 <= fno <= 110 and wt == 2 and isinstance(val, bytes):
            if step.variant_field is None:
                step.variant_field = fno
                step.variant_data = val
    if step.variant_field is not None:
        step.content_text = extract_step_text(step.variant_field, step.variant_data)
    return step


def parse_checkpoint(cp_buf: bytes, step_index: int) -> CheckpointInfo:
    """Parse CortexStepCheckpoint.

    Args:
        cp_buf: Raw bytes of the checkpoint message.
        step_index: Index of the step containing this checkpoint.

    Returns:
        CheckpointInfo with all parsed fields.
    """
    cp = CheckpointInfo(step_index=step_index)
    for fno, wt, _off, val in iter_fields(cp_buf):
        if fno == 1 and wt == 0 and isinstance(val, int):
            cp.checkpoint_index = val
        elif fno == 3:
            if wt == 0 and isinstance(val, int):
                cp.included_step_indices.append(val)
            elif wt == 2 and isinstance(val, bytes):
                pos = 0
                while pos < len(val):
                    v, pos = read_varint(val, pos)
                    cp.included_step_indices.append(v)
        elif fno == 4 and wt == 2 and isinstance(val, bytes):
            cp.user_intent = val.decode("utf-8", errors="replace")
        elif fno == 5 and wt == 2 and isinstance(val, bytes):
            cp.session_summary = val.decode("utf-8", errors="replace")
        elif fno == 6 and wt == 2 and isinstance(val, bytes):
            cp.code_change_summary = val.decode("utf-8", errors="replace")
        elif fno == 7 and wt == 2 and isinstance(val, bytes):
            # edited_file_map entry: {1: key (file path), 2: DiffList}
            for ifno, iwt, _ioff, ival in iter_fields(val):
                if ifno == 1 and iwt == 2 and isinstance(ival, bytes):
                    file_path = ival.decode("utf-8", errors="replace")
                    if file_path:
                        cp.edited_files.append(file_path)
        elif fno == 8 and wt == 2 and isinstance(val, bytes):
            cp.memory_summary = val.decode("utf-8", errors="replace")
        elif fno == 9 and wt == 0 and isinstance(val, int):
            cp.intent_only = bool(val)
        elif fno == 10 and wt == 2 and isinstance(val, bytes):
            cp.conversation_title = val.decode("utf-8", errors="replace")
        elif fno == 11 and wt == 0 and isinstance(val, int):
            cp.included_step_index_start = val
        elif fno == 12 and wt == 0 and isinstance(val, int):
            cp.included_step_index_end = val
        elif fno == 13 and wt == 2 and isinstance(val, bytes):
            cp.plan_snapshot = val.decode("utf-8", errors="replace")
    return cp


def group_rounds(steps: list[StepInfo]) -> list[RoundInfo]:
    """Group steps into conversation rounds.

    A new round starts at each user_input step (variant_field == 19).
    If no user_input steps exist, all steps form a single round.

    Args:
        steps: List of parsed StepInfo in order.

    Returns:
        List of RoundInfo.
    """
    rounds: list[RoundInfo] = []
    round_start: int | None = None
    round_prompt = ""
    round_num = 0

    for step in steps:
        if step.variant_field == VARIANT_USER_INPUT:
            if round_start is not None:
                rounds.append(
                    RoundInfo(
                        round_number=round_num,
                        prompt=round_prompt,
                        start_step=round_start,
                        end_step=step.index - 1,
                    )
                )
            round_num += 1
            round_start = step.index
            round_prompt = step.content_text

    if round_start is not None:
        last_idx = steps[-1].index if steps else round_start
        rounds.append(
            RoundInfo(
                round_number=round_num,
                prompt=round_prompt,
                start_step=round_start,
                end_step=last_idx,
            )
        )

    return rounds


def parse(plaintext: bytes) -> TrajectoryInfo:
    """Parse decrypted protobuf bytes into a TrajectoryInfo.

    Args:
        plaintext: Decrypted protobuf bytes (CortexTrajectory).

    Returns:
        TrajectoryInfo with metadata, steps, checkpoints, and rounds.
    """
    meta = parse_trajectory_metadata(plaintext)
    traj = TrajectoryInfo(
        trajectory_id=meta["trajectory_id"],
        cascade_id=meta["cascade_id"],
        trajectory_type=meta["trajectory_type"],
        source=meta["source"],
        project_path=meta["project_path"],
        git_branch=meta["git_branch"],
    )

    for idx, step_buf in enumerate(meta["steps"]):
        step = parse_step(step_buf, idx)
        traj.steps.append(step)

        if step.variant_field == VARIANT_CHECKPOINT:
            cp = parse_checkpoint(step.variant_data, idx)
            traj.checkpoints.append(cp)

        if step.model and not traj.model:
            traj.model = step.model

    traj.rounds = group_rounds(traj.steps)
    return traj


def parse_file(bin_path: Path) -> TrajectoryInfo:
    """Parse a decrypted .bin file.

    Args:
        bin_path: Path to decrypted protobuf file.

    Returns:
        TrajectoryInfo.
    """
    return parse(bin_path.read_bytes())

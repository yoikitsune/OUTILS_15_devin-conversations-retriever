"""Devin Local SQLite reader.

Reads conversations from the Devin Local `sessions.db` SQLite database
(`~/.local/share/devin/cli/sessions.db`) and converts them into
`TrajectoryInfo` objects that the existing indexer can store.

Key design points (see ADR-0005 for full rationale):

- **Full-tree indexing**: every `message_nodes` row for a session becomes a
  `StepInfo`. Lateral branches (regenerations, edited prompts) are preserved
  — they are the signal needed to diagnose Devin Local's behaviour.
- **Main-chain flag**: `on_main_chain` is computed by walking from
  `sessions.main_chain_id` (tip) back to root via `parent_node_id`. This
  lets `dcr show` render the linear conversation the user saw, while
  `--full-tree` (Phase 2) surfaces lateral branches.
- **Compaction checkpoints**: nodes whose `metadata.extensions` contains
  `compact/prior_node_ids` are recorded as `CheckpointInfo` rows.
- **JSON parsing**: `message_nodes.chat_message` is a JSON string. The keys
  `role`, `content`, `thinking`, `tool_calls`, `tool_call_id` live *inside*
  that JSON, NOT as SQL columns. `thinking` is a nested object
  (`chat_message.thinking.thinking` holds the reasoning text).
- **Read-only**: `sessions.db` is opened with `mode=ro` to avoid lock
  contention with the running Devin Local process.
- **Schema version**: `refinery_schema_history` is read to detect schema
  evolution. The schema is additive, so unknown columns are ignored.

Verified 2026-07-31 against the real `sessions.db` (104 sessions, 6575
message_nodes, schema version 16).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from dcr.parser import CheckpointInfo, StepInfo, TrajectoryInfo

logger = logging.getLogger(__name__)

DEFAULT_DEVIN_LOCAL_DB = Path.home() / ".local" / "share" / "devin" / "cli" / "sessions.db"

# Known Devin Local schema version (refinery). Higher versions are tolerated
# (additive migrations) with a warning — see ADR-0005 D4.
KNOWN_SCHEMA_VERSION = 16

# Role → variant_field mapping (mirrors Cascade variant numbers so the
# existing CLI/search code, which keys off variant_field, works unchanged).
# See ADR-0005 "Devin Local → dcr mapping".
_ROLE_VARIANT: dict[str, int] = {
    "user": 19,        # VARIANT_USER_INPUT
    "assistant": 20,   # VARIANT_PLANNER_RESPONSE
    "system": 0,       # no Cascade equivalent
    "tool": 37,        # VARIANT_COMMAND_RESULT
}


class DevinLocalReader:
    """Read conversations from a Devin Local ``sessions.db`` database.

    The database is opened read-only (``mode=ro`` URI) so it can be read
    safely while Devin Local is writing to it.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize the reader.

        Args:
            db_path: Path to the Devin Local ``sessions.db`` file.
                If None, uses ``DEFAULT_DEVIN_LOCAL_DB``.
        """
        if db_path is None:
            db_path = DEFAULT_DEVIN_LOCAL_DB
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy read-only connection to ``sessions.db``."""
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Devin Local DB not found: {self.db_path}")
            # mode=ro avoids lock contention with the running Devin Local.
            uri = f"file:{self.db_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> DevinLocalReader:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # --- Schema versioning (ADR-0005 D4) ---

    def schema_version(self) -> int | None:
        """Return the current Devin Local refinery schema version.

        Returns:
            The highest version from ``refinery_schema_history``, or None if
            the table is absent.
        """
        try:
            cur = self.conn.execute(
                "SELECT MAX(version) FROM refinery_schema_history"
            )
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            return None

    def check_schema(self) -> int | None:
        """Check the schema version and warn if higher than known.

        Returns:
            The detected schema version.
        """
        version = self.schema_version()
        if version is not None and version > KNOWN_SCHEMA_VERSION:
            logger.warning(
                "Devin Local schema version %d is higher than known version "
                "%d. Attempting sync anyway (schema is additive).",
                version,
                KNOWN_SCHEMA_VERSION,
            )
        return version

    # --- Reading ---

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with their metadata.

        Returns:
            List of dicts with keys: id, title, model, agent_mode,
            working_directory, created_at, last_activity_at, main_chain_id,
            metadata (parsed JSON dict).
        """
        cur = self.conn.execute(
            """SELECT id, title, model, agent_mode, working_directory,
                      created_at, last_activity_at, main_chain_id, metadata
               FROM sessions ORDER BY last_activity_at ASC"""
        )
        rows: list[dict[str, Any]] = []
        for sid, title, model, mode, wd, created, activity, mc_id, meta in cur.fetchall():
            rows.append(
                {
                    "id": sid,
                    "title": title,
                    "model": model,
                    "agent_mode": mode,
                    "working_directory": wd,
                    "created_at": created,
                    "last_activity_at": activity,
                    "main_chain_id": mc_id,
                    "metadata": _safe_json(meta),
                }
            )
        return rows

    def read_session(self, session_id: str) -> TrajectoryInfo | None:
        """Read a single session and convert it to ``TrajectoryInfo``.

        Full-tree indexing: every ``message_nodes`` row becomes a ``StepInfo``.
        ``on_main_chain`` is computed via a tip→root walk on
        ``parent_node_id`` starting from ``sessions.main_chain_id``.
        Compaction nodes (``metadata.extensions["compact/prior_node_ids"]``)
        are recorded as ``CheckpointInfo``.

        Args:
            session_id: The session slug (``sessions.id``).

        Returns:
            ``TrajectoryInfo`` with ``source_type='devin_local'``, or None if
            the session does not exist.
        """
        cur = self.conn.execute(
            """SELECT id, title, model, agent_mode, working_directory,
                      created_at, last_activity_at, main_chain_id, metadata
               FROM sessions WHERE id = ?""",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        sid, title, model, mode, wd, created, activity, mc_id, meta = row
        meta_dict = _safe_json(meta)

        # Fetch all nodes ordered by created_at ASC, node_id ASC.
        # Verified: node_id alone is NOT chronological (3705 inversions on a
        # 466-node session), so created_at must lead.
        cur = self.conn.execute(
            """SELECT node_id, parent_node_id, chat_message, created_at, metadata
               FROM message_nodes WHERE session_id = ?
               ORDER BY created_at ASC, node_id ASC""",
            (session_id,),
        )
        node_rows = cur.fetchall()

        # Build parent map for the main-chain walk.
        parents: dict[int, int | None] = {}
        for nid, pid, _cm, _ts, _md in node_rows:
            parents[nid] = pid
        main_chain = _main_chain_set(mc_id, parents)

        steps: list[StepInfo] = []
        checkpoints: list[CheckpointInfo] = []
        for idx, (nid, pid, cm, ts, md) in enumerate(node_rows):
            cm_dict = _safe_json(cm)
            md_dict = _safe_json(md)
            role = cm_dict.get("role") or ""
            content = cm_dict.get("content") or ""
            thinking = _extract_thinking(cm_dict.get("thinking"))
            tool_calls = cm_dict.get("tool_calls")
            tool_calls_json = json.dumps(tool_calls) if tool_calls else None
            tool_call_id = cm_dict.get("tool_call_id")

            steps.append(
                StepInfo(
                    index=idx,
                    variant_field=_ROLE_VARIANT.get(role),
                    content_text=content,
                    timestamp=float(ts) if ts is not None else None,
                    model=model or "",
                    role=role,
                    thinking=thinking,
                    tool_calls_json=tool_calls_json,
                    tool_call_id=tool_call_id,
                    node_id=nid,
                    parent_node_id=pid,
                    on_main_chain=1 if nid in main_chain else 0,
                )
            )

            # Compaction checkpoint: metadata.extensions["compact/prior_node_ids"]
            ext = md_dict.get("extensions") or {}
            prior_ids = ext.get("compact/prior_node_ids")
            if prior_ids:
                checkpoints.append(
                    CheckpointInfo(
                        step_index=nid,
                        checkpoint_index=len(checkpoints),
                        session_summary=content,
                        included_step_index_start=min(prior_ids),
                        included_step_index_end=max(prior_ids),
                        included_step_indices=list(prior_ids),
                    )
                )

        traj = TrajectoryInfo(
            trajectory_id=sid,
            cascade_id=sid,  # universal ID column
            project_path=wd or "",
            model=model or "",
            steps=steps,
            checkpoints=checkpoints,
            source_type="devin_local",
            agent_mode=mode,
            credit_cost=_extract_cost(meta_dict, "total_credit_cost"),
            acu_cost=_extract_cost(meta_dict, "total_acu_cost"),
            # Authoritative session-level timestamps/title from sessions.db.
            created_at_override=float(created) if created is not None else None,
            updated_at_override=float(activity) if activity is not None else None,
            title_override=title or None,
        )
        return traj

    def read_sessions(self) -> list[TrajectoryInfo]:
        """Read all sessions and convert them to ``TrajectoryInfo`` objects.

        Returns:
            List of ``TrajectoryInfo`` ordered by ``last_activity_at`` ASC.
        """
        self.check_schema()
        sessions = self.list_sessions()
        return [traj for s in sessions if (traj := self.read_session(s["id"])) is not None]


# --- Helpers ---


def _safe_json(text: str | None) -> dict[str, Any]:
    """Parse a JSON string, returning ``{}`` on failure or None input."""
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_thinking(thinking: Any) -> str | None:
    """Extract the reasoning text from a ``chat_message.thinking`` value.

    ``thinking`` is a nested object: ``{"thinking": "<text>", "signature": ...}``.
    A bare string is also accepted (defensive).
    """
    if thinking is None:
        return None
    if isinstance(thinking, str):
        return thinking or None
    if isinstance(thinking, dict):
        text = thinking.get("thinking")
        return text if isinstance(text, str) and text else None
    return None


def _extract_cost(meta: dict[str, Any], key: str) -> float | None:
    """Extract a numeric cost from the session metadata dict."""
    val = meta.get(key)
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _main_chain_set(tip: int | None, parents: dict[int, int | None]) -> set[int]:
    """Compute the set of node_ids on the main chain.

    Walks from ``tip`` (``sessions.main_chain_id``) back to root via
    ``parent_node_id``. If ``tip`` is None, returns an empty set (fallback:
    all nodes get ``on_main_chain=0`` and rely on ``created_at`` ordering).

    A cycle guard prevents infinite loops on malformed forests.
    """
    if tip is None:
        return set()
    chain: set[int] = set()
    cur: int | None = tip
    while cur is not None and cur not in chain:
        chain.add(cur)
        cur = parents.get(cur)
    return chain

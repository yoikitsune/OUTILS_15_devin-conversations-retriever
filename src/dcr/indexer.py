"""SQLite + FTS5 indexer for Windsurf Cascade conversations.

Stores parsed trajectory data in SQLite with FTS5 full-text search
on conversation content (prompts, step text, checkpoint summaries).

See docs/architecture.md for schema design.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dcr.parser import TrajectoryInfo

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "dcr" / "dcr.db"
DEFAULT_CASCADE_DIR = Path.home() / ".codeium" / "windsurf" / "cascade"

SCHEMA_SQL = """
-- Main tables
CREATE TABLE IF NOT EXISTS conversations (
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

CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    prompt TEXT,
    start_step INTEGER,
    end_step INTEGER,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    step_index INTEGER NOT NULL,
    type INTEGER,
    status INTEGER,
    variant_field INTEGER,
    content_text TEXT,
    timestamp REAL,
    model TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checkpoints (
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
    edited_files TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- FTS5 virtual tables for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS rounds_fts USING fts5(
    prompt,
    content='rounds',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS steps_fts USING fts5(
    content_text,
    content='steps',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS checkpoints_fts USING fts5(
    user_intent,
    session_summary,
    code_change_summary,
    memory_summary,
    conversation_title,
    content='checkpoints',
    content_rowid='id',
    tokenize='unicode61'
);

-- Triggers to keep FTS5 in sync with main tables
CREATE TRIGGER IF NOT EXISTS rounds_ai AFTER INSERT ON rounds BEGIN
    INSERT INTO rounds_fts(rowid, prompt) VALUES (new.id, new.prompt);
END;

CREATE TRIGGER IF NOT EXISTS rounds_ad AFTER DELETE ON rounds BEGIN
    INSERT INTO rounds_fts(rounds_fts, rowid, prompt) VALUES ('delete', old.id, old.prompt);
END;

CREATE TRIGGER IF NOT EXISTS rounds_au AFTER UPDATE ON rounds BEGIN
    INSERT INTO rounds_fts(rounds_fts, rowid, prompt) VALUES ('delete', old.id, old.prompt);
    INSERT INTO rounds_fts(rowid, prompt) VALUES (new.id, new.prompt);
END;

CREATE TRIGGER IF NOT EXISTS steps_ai AFTER INSERT ON steps BEGIN
    INSERT INTO steps_fts(rowid, content_text) VALUES (new.id, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS steps_ad AFTER DELETE ON steps BEGIN
    INSERT INTO steps_fts(steps_fts, rowid, content_text) VALUES ('delete', old.id, old.content_text);
END;

CREATE TRIGGER IF NOT EXISTS steps_au AFTER UPDATE ON steps BEGIN
    INSERT INTO steps_fts(steps_fts, rowid, content_text) VALUES ('delete', old.id, old.content_text);
    INSERT INTO steps_fts(rowid, content_text) VALUES (new.id, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS checkpoints_ai AFTER INSERT ON checkpoints BEGIN
    INSERT INTO checkpoints_fts(rowid, user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
    VALUES (new.id, new.user_intent, new.session_summary, new.code_change_summary, new.memory_summary, new.conversation_title);
END;

CREATE TRIGGER IF NOT EXISTS checkpoints_ad AFTER DELETE ON checkpoints BEGIN
    INSERT INTO checkpoints_fts(checkpoints_fts, rowid, user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
    VALUES ('delete', old.id, old.user_intent, old.session_summary, old.code_change_summary, old.memory_summary, old.conversation_title);
END;

CREATE TRIGGER IF NOT EXISTS checkpoints_au AFTER UPDATE ON checkpoints BEGIN
    INSERT INTO checkpoints_fts(checkpoints_fts, rowid, user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
    VALUES ('delete', old.id, old.user_intent, old.session_summary, old.code_change_summary, old.memory_summary, old.conversation_title);
    INSERT INTO checkpoints_fts(rowid, user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
    VALUES (new.id, new.user_intent, new.session_summary, new.code_change_summary, new.memory_summary, new.conversation_title);
END;

-- Index for faster cascade_id lookups
CREATE INDEX IF NOT EXISTS idx_conversations_cascade_id ON conversations(cascade_id);
CREATE INDEX IF NOT EXISTS idx_conversations_project_path ON conversations(project_path);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_rounds_conversation_id ON rounds(conversation_id);
CREATE INDEX IF NOT EXISTS idx_steps_conversation_id ON steps(conversation_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_conversation_id ON checkpoints(conversation_id);
"""

MIGRATION_SQL = [
    "ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0",
    "ALTER TABLE conversations ADD COLUMN archived_at TEXT",
    "CREATE INDEX IF NOT EXISTS idx_conversations_archived ON conversations(archived)",
]


class Indexer:
    """SQLite + FTS5 indexer for conversation data."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize the indexer.

        Args:
            db_path: Path to the SQLite database file.
                If None, uses DEFAULT_DB_PATH (~/.local/share/dcr/dcr.db).
        """
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection with foreign keys enabled."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def init_schema(self) -> None:
        """Create database schema if not exists, and run migrations."""
        self.conn.executescript(SCHEMA_SQL)
        for stmt in MIGRATION_SQL:
            try:
                self.conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Indexer:
        self.init_schema()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def is_indexed(self, cascade_id: str, pb_mtime: float, pb_size: int) -> bool:
        """Check if a conversation is already indexed with same mtime and size.

        Args:
            cascade_id: The cascade UUID (filename stem).
            pb_mtime: Modification time of the .pb file.
            pb_size: File size of the .pb file.

        Returns:
            True if already indexed with matching mtime and size.
        """
        cur = self.conn.execute(
            "SELECT pb_mtime, pb_size FROM conversations WHERE cascade_id = ?",
            (cascade_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        return row[0] == pb_mtime and row[1] == pb_size

    def index_trajectory(
        self,
        traj: TrajectoryInfo,
        cascade_id: str,
        pb_mtime: float = 0.0,
        pb_size: int = 0,
    ) -> int:
        """Index a single parsed trajectory into the database.

        If a conversation with the same cascade_id already exists,
        it is replaced and re-indexed (upsert semantics).

        Args:
            traj: Parsed TrajectoryInfo from dcr.parser.
            cascade_id: The cascade UUID (filename stem of the .pb file).
            pb_mtime: Modification time of the source .pb file.
            pb_size: Size of the source .pb file.

        Returns:
            The conversation_id (rowid) of the indexed conversation.
        """
        self.init_schema()

        # Delete existing conversation if any (cascade will clean child rows)
        self.conn.execute(
            "DELETE FROM conversations WHERE cascade_id = ?",
            (cascade_id,),
        )

        # Insert conversation
        cur = self.conn.execute(
            """INSERT INTO conversations
               (cascade_id, trajectory_id, title, trajectory_type, source,
                project_path, git_branch, model, created_at, updated_at,
                step_count, round_count, checkpoint_count, pb_mtime, pb_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cascade_id,
                traj.trajectory_id,
                traj.title,
                traj.trajectory_type,
                traj.source,
                traj.project_path,
                traj.git_branch,
                traj.model,
                traj.created_at,
                traj.updated_at,
                traj.step_count,
                traj.round_count,
                len(traj.checkpoints),
                pb_mtime,
                pb_size,
            ),
        )
        conv_id = cur.lastrowid

        # Insert rounds
        for rnd in traj.rounds:
            self.conn.execute(
                """INSERT INTO rounds
                   (conversation_id, round_number, prompt, start_step, end_step)
                   VALUES (?, ?, ?, ?, ?)""",
                (conv_id, rnd.round_number, rnd.prompt, rnd.start_step, rnd.end_step),
            )

        # Insert steps
        for step in traj.steps:
            self.conn.execute(
                """INSERT INTO steps
                   (conversation_id, step_index, type, status, variant_field,
                    content_text, timestamp, model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    conv_id,
                    step.index,
                    step.type,
                    step.status,
                    step.variant_field,
                    step.content_text,
                    step.timestamp,
                    step.model,
                ),
            )

        # Insert checkpoints
        for cp in traj.checkpoints:
            self.conn.execute(
                """INSERT INTO checkpoints
                   (conversation_id, step_index, checkpoint_index,
                    user_intent, session_summary, code_change_summary,
                    memory_summary, conversation_title, plan_snapshot,
                    intent_only, included_step_index_start, included_step_index_end,
                    edited_files)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    conv_id,
                    cp.step_index,
                    cp.checkpoint_index,
                    cp.user_intent,
                    cp.session_summary,
                    cp.code_change_summary,
                    cp.memory_summary,
                    cp.conversation_title,
                    cp.plan_snapshot,
                    int(cp.intent_only),
                    cp.included_step_index_start,
                    cp.included_step_index_end,
                    "\n".join(cp.edited_files),
                ),
            )

        self.conn.commit()
        return conv_id

    def index_file(
        self,
        pb_path: Path,
        plaintext: bytes | None = None,
    ) -> int | None:
        """Decrypt, parse, and index a single .pb file.

        Args:
            pb_path: Path to the .pb file.
            plaintext: Pre-decrypted plaintext bytes. If None, decrypts from pb_path.

        Returns:
            conversation_id if indexed, None if skipped (already up-to-date).
        """
        from dcr.decrypt import decrypt_file
        from dcr.parser import parse

        self.init_schema()

        stat = pb_path.stat()
        cascade_id = pb_path.stem

        if self.is_indexed(cascade_id, stat.st_mtime, stat.st_size):
            return None

        if plaintext is None:
            plaintext = decrypt_file(pb_path)

        traj = parse(plaintext)
        return self.index_trajectory(
            traj,
            cascade_id=cascade_id,
            pb_mtime=stat.st_mtime,
            pb_size=stat.st_size,
        )

    def index_directory(
        self,
        input_dir: Path,
        force: bool = False,
    ) -> tuple[int, int, int, list[str]]:
        """Index all .pb files in a directory.

        Args:
            input_dir: Directory containing .pb files.
            force: If True, re-index all files even if unchanged.

        Returns:
            Tuple of (indexed_count, skipped_count, failed_count, error_messages).
        """
        from dcr.decrypt import decrypt_file
        from dcr.parser import parse

        self.init_schema()

        ok = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        for pb_path in sorted(input_dir.glob("*.pb")):
            try:
                stat = pb_path.stat()
                cascade_id = pb_path.stem

                if not force and self.is_indexed(cascade_id, stat.st_mtime, stat.st_size):
                    skipped += 1
                    continue

                traj = parse(decrypt_file(pb_path))
                self.index_trajectory(
                    traj,
                    cascade_id=cascade_id,
                    pb_mtime=stat.st_mtime,
                    pb_size=stat.st_size,
                )
                ok += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{pb_path.name}: {exc}")

        return ok, skipped, failed, errors

    def sync(
        self,
        cascade_dir: Path | None = None,
        remove_stale: bool = False,
    ) -> dict[str, Any]:
        """Synchronize the database with the cascade directory.

        Scans for new/modified .pb files and indexes them.
        Conversations whose .pb file no longer exists are marked as
        archived (archived=1) but are NEVER deleted from the database.

        Args:
            cascade_dir: Directory containing .pb files.
                If None, uses DEFAULT_CASCADE_DIR.
            remove_stale: Deprecated, ignored. Kept for backward compatibility.
                Stale conversations are always archived, never deleted.

        Returns:
            Dict with keys: new, updated, unchanged, archived, failed, errors.
        """
        from dcr.decrypt import decrypt_file
        from dcr.parser import parse

        if cascade_dir is None:
            cascade_dir = DEFAULT_CASCADE_DIR

        self.init_schema()

        # Scan .pb files on disk
        pb_files = {p.stem: p for p in cascade_dir.glob("*.pb")}

        # Get all indexed cascade_ids
        cur = self.conn.execute("SELECT cascade_id FROM conversations")
        indexed_ids = {row[0] for row in cur.fetchall()}

        new = 0
        updated = 0
        unchanged = 0
        archived = 0
        failed = 0
        errors: list[str] = []

        # Index new/modified files
        for cascade_id, pb_path in sorted(pb_files.items()):
            try:
                stat = pb_path.stat()
                if self.is_indexed(cascade_id, stat.st_mtime, stat.st_size):
                    unchanged += 1
                    continue

                was_indexed = cascade_id in indexed_ids
                traj = parse(decrypt_file(pb_path))
                self.index_trajectory(
                    traj,
                    cascade_id=cascade_id,
                    pb_mtime=stat.st_mtime,
                    pb_size=stat.st_size,
                )
                if was_indexed:
                    updated += 1
                else:
                    new += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{pb_path.name}: {exc}")

        # Archive conversations whose .pb file no longer exists (never delete)
        stale_ids = indexed_ids - set(pb_files.keys())
        for cascade_id in stale_ids:
            self.conn.execute(
                "UPDATE conversations SET archived = 1, archived_at = datetime('now') "
                "WHERE cascade_id = ? AND archived = 0",
                (cascade_id,),
            )
            archived += 1
        if archived > 0:
            self.conn.commit()

        return {
            "new": new,
            "updated": updated,
            "unchanged": unchanged,
            "archived": archived,
            "failed": failed,
            "errors": errors,
        }

    def get_status(self) -> dict[str, Any]:
        """Return indexing status and statistics.

        Returns:
            Dict with conversation_count, step_count, round_count,
            checkpoint_count, db_path, db_size.
        """
        cur = self.conn.execute(
            """SELECT
                (SELECT COUNT(*) FROM conversations) as conv_count,
                (SELECT COUNT(*) FROM conversations WHERE archived = 0) as active_count,
                (SELECT COUNT(*) FROM conversations WHERE archived = 1) as archived_count,
                (SELECT COUNT(*) FROM steps) as step_count,
                (SELECT COUNT(*) FROM rounds) as round_count,
                (SELECT COUNT(*) FROM checkpoints) as cp_count"""
        )
        row = cur.fetchone()
        conv_count, active_count, archived_count, step_count, round_count, cp_count = row

        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "conversation_count": conv_count,
            "active_count": active_count,
            "archived_count": archived_count,
            "step_count": step_count,
            "round_count": round_count,
            "checkpoint_count": cp_count,
            "db_path": str(self.db_path),
            "db_size": db_size,
        }

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        """List indexed conversations.

        Args:
            limit: Maximum number of conversations to return.

        Returns:
            List of dicts with conversation metadata.
        """
        cur = self.conn.execute(
            """SELECT id, cascade_id, trajectory_id, title,
                      step_count, round_count, checkpoint_count,
                      project_path, git_branch, model, created_at, updated_at,
                      pb_mtime, indexed_at, archived, archived_at
               FROM conversations
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        )
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_conversation(self, cascade_id: str) -> dict[str, Any] | None:
        """Get a conversation with its rounds, steps, and checkpoints.

        Args:
            cascade_id: The cascade UUID.

        Returns:
            Dict with conversation metadata and nested rounds, steps, checkpoints.
            None if not found.
        """
        cur = self.conn.execute(
            "SELECT id FROM conversations WHERE cascade_id = ?",
            (cascade_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        conv_id = row[0]

        # Conversation metadata
        cur = self.conn.execute(
            """SELECT id, cascade_id, trajectory_id, title,
                      trajectory_type, source, project_path, git_branch, model,
                      created_at, updated_at, step_count, round_count,
                      checkpoint_count, pb_mtime, indexed_at,
                      archived, archived_at
               FROM conversations WHERE id = ?""",
            (conv_id,),
        )
        columns = [d[0] for d in cur.description]
        conv = dict(zip(columns, cur.fetchone()))

        # Rounds
        cur = self.conn.execute(
            """SELECT id, round_number, prompt, start_step, end_step
               FROM rounds WHERE conversation_id = ?
               ORDER BY round_number""",
            (conv_id,),
        )
        columns = [d[0] for d in cur.description]
        conv["rounds"] = [dict(zip(columns, row)) for row in cur.fetchall()]

        # Steps
        cur = self.conn.execute(
            """SELECT id, step_index, type, status, variant_field,
                      content_text, timestamp, model
               FROM steps WHERE conversation_id = ?
               ORDER BY step_index""",
            (conv_id,),
        )
        columns = [d[0] for d in cur.description]
        conv["steps"] = [dict(zip(columns, row)) for row in cur.fetchall()]

        # Checkpoints
        cur = self.conn.execute(
            """SELECT id, step_index, checkpoint_index,
                      user_intent, session_summary, code_change_summary,
                      memory_summary, conversation_title, edited_files
               FROM checkpoints WHERE conversation_id = ?
               ORDER BY step_index""",
            (conv_id,),
        )
        columns = [d[0] for d in cur.description]
        conv["checkpoints"] = [dict(zip(columns, row)) for row in cur.fetchall()]

        return conv

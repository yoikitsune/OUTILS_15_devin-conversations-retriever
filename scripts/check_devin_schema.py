#!/usr/bin/env python3
"""Check Devin Local sessions.db schema compatibility with dcr.

Verifies that the local ``sessions.db`` schema is compatible with the
version of ``dcr`` installed. Checks:

1. **Schema version**: ``refinery_schema_history`` version ≤ KNOWN_SCHEMA_VERSION
2. **Required tables**: ``sessions``, ``message_nodes``, ``refinery_schema_history``
3. **Required columns**: all columns that ``devin_local.py`` reads
4. **chat_message JSON keys**: role, content present in a sample node

Exit codes:
    0 — schema is compatible (or sessions.db not found, which is OK)
    1 — schema is ahead of known version (warning, may still work — additive)
    2 — schema is incompatible (missing tables or columns — sync will fail)

Usage::

    python scripts/check_devin_schema.py [--db PATH] [--json]

    --db PATH   Override sessions.db path (default: ~/.local/share/devin/cli/sessions.db)
    --json      Output as JSON instead of human-readable text
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Import from dcr package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dcr.devin_local import DEFAULT_DEVIN_LOCAL_DB, KNOWN_SCHEMA_VERSION  # noqa: E402


# Required tables and their required columns (what devin_local.py reads).
REQUIRED_TABLES: dict[str, list[str]] = {
    "sessions": [
        "id", "title", "model", "agent_mode", "working_directory",
        "created_at", "last_activity_at", "main_chain_id", "metadata",
    ],
    "message_nodes": [
        "row_id", "session_id", "node_id", "parent_node_id",
        "chat_message", "created_at", "metadata",
    ],
    "refinery_schema_history": [
        "version",
    ],
}

# Required JSON keys in chat_message (what devin_local.py parses).
REQUIRED_CHAT_KEYS = {"role", "content"}


def check_schema(db_path: Path) -> dict:
    """Check schema compatibility and return a report dict.

    Returns:
        Dict with keys: db_path, exists, schema_version, known_version,
        status, tables (dict of table → {ok, missing_columns}),
        chat_message_keys_ok, errors, warnings.
    """
    report: dict = {
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "schema_version": None,
        "known_version": KNOWN_SCHEMA_VERSION,
        "status": "ok",
        "tables": {},
        "chat_message_keys_ok": None,
        "errors": [],
        "warnings": [],
    }

    if not db_path.exists():
        report["status"] = "not_found"
        return report

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        report["status"] = "error"
        report["errors"].append(f"Cannot open database: {e}")
        return report

    # 1. Schema version
    try:
        cur = conn.execute("SELECT MAX(version) FROM refinery_schema_history")
        row = cur.fetchone()
        version = row[0] if row else None
        report["schema_version"] = version
        if version is not None and version > KNOWN_SCHEMA_VERSION:
            report["status"] = "ahead"
            report["warnings"].append(
                f"Schema version {version} is ahead of known version "
                f"{KNOWN_SCHEMA_VERSION}. Sync may miss new fields "
                f"(schema is additive — existing fields should still work)."
            )
    except sqlite3.OperationalError:
        report["warnings"].append("refinery_schema_history table not found — cannot check version.")

    # 2. Required tables and columns
    for table, required_cols in REQUIRED_TABLES.items():
        try:
            cur = conn.execute(f"PRAGMA table_info({table})")
            actual_cols = {row[1] for row in cur.fetchall()}
        except sqlite3.OperationalError:
            report["tables"][table] = {"ok": False, "missing_columns": required_cols}
            report["errors"].append(f"Required table '{table}' is missing.")
            report["status"] = "incompatible"
            continue

        missing = [c for c in required_cols if c not in actual_cols]
        report["tables"][table] = {"ok": len(missing) == 0, "missing_columns": missing}
        if missing:
            report["errors"].append(
                f"Table '{table}' is missing columns: {', '.join(missing)}"
            )
            report["status"] = "incompatible"

    # 3. chat_message JSON keys (sample one node)
    if report["tables"].get("message_nodes", {}).get("ok", False):
        try:
            cur = conn.execute(
                "SELECT chat_message FROM message_nodes LIMIT 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                msg = json.loads(row[0])
                actual_keys = set(msg.keys()) if isinstance(msg, dict) else set()
                missing_keys = REQUIRED_CHAT_KEYS - actual_keys
                report["chat_message_keys_ok"] = len(missing_keys) == 0
                if missing_keys:
                    report["errors"].append(
                        f"chat_message JSON is missing required keys: {', '.join(missing_keys)}"
                    )
                    report["status"] = "incompatible"
            else:
                report["chat_message_keys_ok"] = None
                report["warnings"].append("No message_nodes rows to sample chat_message JSON.")
        except (json.JSONDecodeError, sqlite3.OperationalError) as e:
            report["chat_message_keys_ok"] = False
            report["errors"].append(f"Cannot parse chat_message JSON: {e}")
            report["status"] = "incompatible"

    conn.close()

    # Final status: if errors exist, it's incompatible; if only warnings, it's ahead/ok
    if report["errors"]:
        report["status"] = "incompatible"
    elif report["warnings"] and report["status"] != "ahead":
        report["status"] = "ok"  # warnings but no errors

    return report


def format_report(report: dict) -> str:
    """Format the report as human-readable text."""
    lines: list[str] = []
    db_path = report["db_path"]
    lines.append(f"Devin Local schema check")
    lines.append(f"  DB path:    {db_path}")

    if not report["exists"]:
        lines.append(f"  Status:     not found (OK — no sessions.db to check)")
        return "\n".join(lines)

    version = report["schema_version"]
    known = report["known_version"]
    status = report["status"]

    status_emoji = {
        "ok": "✓",
        "ahead": "⚠",
        "incompatible": "✗",
        "not_found": "—",
        "error": "✗",
    }.get(status, "?")

    lines.append(f"  Schema:     detected v{version}, known v{known}  {status_emoji}")
    lines.append(f"  Status:     {status}")

    # Tables
    for table, info in report["tables"].items():
        if info["ok"]:
            lines.append(f"  {table}: ✓ all required columns present")
        else:
            missing = ", ".join(info["missing_columns"])
            lines.append(f"  {table}: ✗ missing columns: {missing}")

    # chat_message keys
    ck = report["chat_message_keys_ok"]
    if ck is True:
        lines.append(f"  chat_message JSON: ✓ required keys present")
    elif ck is False:
        lines.append(f"  chat_message JSON: ✗ missing required keys")

    # Warnings
    for w in report["warnings"]:
        lines.append(f"  ⚠ {w}")

    # Errors
    for e in report["errors"]:
        lines.append(f"  ✗ {e}")

    return "\n".join(lines)


def main() -> int:
    """Entry point for the schema check script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check Devin Local sessions.db schema compatibility with dcr."
    )
    parser.add_argument(
        "--db", default=str(DEFAULT_DEVIN_LOCAL_DB),
        help=f"Path to sessions.db (default: {DEFAULT_DEVIN_LOCAL_DB})",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Output as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    report = check_schema(db_path)

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_report(report))

    # Exit code: 0=ok/not_found, 1=ahead (warning), 2=incompatible
    status = report["status"]
    if status == "incompatible":
        return 2
    elif status == "ahead":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

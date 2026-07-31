"""CLI interface for Devin Conversations Retriever (dcr).

Subcommands:
  sync     — Sync database with cascade .pb files
  search   — Full-text search conversations
  list     — List indexed conversations
  show     — Show a specific conversation
  export   — Export a conversation as structured markdown
  status   — Show database status
  html     — Generate HTML overview
"""

from __future__ import annotations

import argparse
import datetime
import html as html_mod
import sys
from datetime import datetime as dt
from pathlib import Path
from typing import Any, Sequence

from dcr.indexer import DEFAULT_DB_PATH, Indexer
from dcr.parser import (
    VARIANT_USER_INPUT,
    VARIANT_PLANNER_RESPONSE,
    VARIANT_RUN_COMMAND,
    VARIANT_CHECKPOINT,
    VARIANT_COMMAND_RESULT,
)
from dcr.search import SearchEngine


_VARIANT_LABELS: dict[int, str] = {
    VARIANT_USER_INPUT: "user_input",
    VARIANT_PLANNER_RESPONSE: "planner_response",
    VARIANT_RUN_COMMAND: "run_command",
    VARIANT_CHECKPOINT: "checkpoint",
    VARIANT_COMMAND_RESULT: "command_result",
}


def _parse_date(s: str) -> float:
    """Parse a date string (YYYY-MM-DD or YYYY-MM-DD HH:MM) to Unix timestamp."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Invalid date format: '{s}'. Use YYYY-MM-DD or YYYY-MM-DD HH:MM")


# --- Helpers ---


def _fmt_ts(ts: float | None) -> str:
    """Format a Unix timestamp as YYYY-MM-DD HH:MM."""
    if ts is None:
        return "—"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences for clean output."""
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# --- Subcommands ---


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync database with Cascade .pb files and Devin Local sessions.db."""
    idx = Indexer(db_path=args.db_path)
    result = idx.sync()
    idx.close()

    print(f"Sync complete:")
    print(f"  New:       {result['new']}")
    print(f"  Updated:   {result['updated']}")
    print(f"  Unchanged: {result['unchanged']}")
    print(f"  Archived:  {result['archived']}")
    # Per-source breakdown (ADR-0005).
    sources = result.get("sources") or {}
    if sources:
        parts = []
        for src in ("cascade", "devin_local"):
            s = sources.get(src, {})
            n = s.get("new", 0)
            u = s.get("updated", 0)
            if n or u:
                parts.append(f"{src}: +{n} new, {u} updated")
        if parts:
            print(f"  Sources:   {'; '.join(parts)}")
    if result["failed"]:
        print(f"  Failed:    {result['failed']}")
        for err in result["errors"][:10]:
            print(f"    {err}")
        if len(result["errors"]) > 10:
            print(f"    ... and {len(result['errors']) - 10} more")
    return 0 if result["failed"] == 0 else 1


def cmd_search(args: argparse.Namespace) -> int:
    """Full-text search conversations."""
    engine = SearchEngine(db_path=args.db_path, auto_sync=not args.no_sync)
    results = engine.search(
        query=args.query,
        limit=args.limit,
        project=args.project,
        date_from=args.date_from,
        date_to=args.date_to,
        source_table=args.source,
    )
    engine.close()

    if results.sync_info:
        s = results.sync_info
        if s["new"] or s["updated"] or s["archived"]:
            print(f"Synced: +{s['new']} new, {s['updated']} updated, {s['archived']} archived")
            print()

    if results.total == 0:
        print("No results found.")
        return 0

    print(f"Found {results.total} match(es), showing {len(results.results)}:\n")

    for i, r in enumerate(results.results, 1):
        project = _truncate(r.project_path, 40) if r.project_path else "—"
        location = ""
        if r.round_number is not None:
            location = f"round {r.round_number}"
        elif r.step_index is not None:
            location = f"step {r.step_index}"

        print(f"{i:3d}. [{r.source_table}] {r.title}")
        print(f"     Project: {project} | {location} | score: {r.score:.3f}")
        snippet = _strip_ansi(r.snippet).strip()
        if snippet:
            print(f"     {snippet}")
        print()

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List indexed conversations."""
    idx = Indexer(db_path=args.db_path)
    idx.init_schema()
    if not args.no_sync:
        idx.sync()
    convs = idx.list_conversations(limit=args.limit, project=args.project)
    idx.close()

    if not convs:
        print("No conversations indexed. Run 'dcr sync' first.")
        return 0

    # Table header
    print(f"{'ID':>3}  {'Src':4s}  {'Created':12s}  {'Updated':12s}  {'Project':30s}  {'Branch':25s}  {'Model':15s}  Title")
    print("-" * 136)

    for c in convs:
        project = _truncate(c["project_path"].replace("/home/julien/Sources/", "~/Sources/") if c["project_path"] else "—", 30)
        branch = _truncate(c["git_branch"] or "—", 25)
        model = _truncate(c["model"] or "—", 15)
        title = _truncate(c["title"] or "—", 40)
        created = _fmt_ts(c["created_at"])
        updated = _fmt_ts(c["updated_at"])
        src = (c.get("source_type") or "cascade")[:4]
        print(f"{c['id']:3d}  {src:4s}  {created:12s}  {updated:12s}  {project:30s}  {branch:25s}  {model:15s}  {title}")

    print(f"\nTotal: {len(convs)} conversation(s)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show a specific conversation."""
    idx = Indexer(db_path=args.db_path)
    idx.init_schema()
    if not args.no_sync:
        idx.sync()
    conv = idx.get_conversation(args.cascade_id)
    idx.close()

    if conv is None:
        print(f"Conversation '{args.cascade_id}' not found.")
        return 1

    # Header
    src = conv.get("source_type") or "cascade"
    print(f"Conversation: {conv['title']}")
    print(f"  ID:          {conv['cascade_id']}  (source: {src})")
    if src == "devin_local":
        mode = conv.get("agent_mode") or "—"
        credit = conv.get("credit_cost")
        acu = conv.get("acu_cost")
        costs = []
        if credit is not None:
            costs.append(f"credit={credit}")
        if acu is not None:
            costs.append(f"acu={acu}")
        cost_str = f"  | costs: {', '.join(costs)}" if costs else ""
        print(f"  Agent mode:  {mode}{cost_str}")
    print(f"  Project:     {conv['project_path'] or '—'}")
    print(f"  Branch:      {conv['git_branch'] or '—'}")
    print(f"  Model:       {conv['model'] or '—'}")
    print(f"  Created:     {_fmt_ts(conv['created_at'])}")
    print(f"  Updated:     {_fmt_ts(conv['updated_at'])}")
    print(f"  Steps:       {conv['step_count']}")
    print(f"  Rounds:      {conv['round_count']}")
    print(f"  Checkpoints: {conv['checkpoint_count']}")
    print()

    # Rounds
    if conv.get("rounds"):
        print("Rounds:")
        for rnd in conv["rounds"]:
            prompt = _truncate(rnd["prompt"] or "(no prompt)", 70)
            print(f"  #{rnd['round_number']:3d}  steps {rnd['start_step']}-{rnd['end_step']}  {prompt}")
        print()

    # Steps (show first N)
    if conv.get("steps"):
        max_show = args.steps if args.steps else 20
        steps = conv["steps"][:max_show]
        print(f"Steps (showing {len(steps)} of {conv['step_count']}):")
        for s in steps:
            text = _truncate(s["content_text"] or "(empty)", 70)
            ts = _fmt_ts(s["timestamp"]) if s.get("timestamp") else ""
            model = s.get("model") or ""
            role = s.get("role") or ""
            role_tag = f" [{role}]" if role else ""
            on_main = s.get("on_main_chain")
            branch_tag = "" if on_main is None else ("  " if on_main else "  ~")
            vf = s["variant_field"]
            vf_str = "?" if vf is None else str(vf)
            print(f"  #{s['step_index']:3d}  v={vf_str:>3}  {ts:12s}  {model:10s}  {text}{role_tag}{branch_tag}")
        if len(conv["steps"]) > max_show:
            print(f"  ... and {len(conv['steps']) - max_show} more steps")
        print()

    # Checkpoints
    if conv.get("checkpoints"):
        print("Checkpoints:")
        for cp in conv["checkpoints"]:
            intent = _truncate(cp["user_intent"] or "—", 70)
            print(f"  step {cp['step_index']:3d}  intent: {intent}")
        print()

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export a conversation as structured markdown."""
    idx = Indexer(db_path=args.db_path)
    idx.init_schema()
    if not args.no_sync:
        idx.sync()
    conv = idx.get_conversation(args.cascade_id)
    idx.close()

    if conv is None:
        print(f"Conversation '{args.cascade_id}' not found.")
        return 1

    lines: list[str] = []

    def _add(text: str = "") -> None:
        lines.append(text)

    # Header
    src = conv.get("source_type") or "cascade"
    _add(f"# {conv['title'] or conv['cascade_id']}")
    _add()
    _add(f"- **ID**: `{conv['cascade_id']}` (source: {src})")
    if src == "devin_local":
        mode = conv.get("agent_mode") or "—"
        _add(f"- **Agent mode**: {mode}")
        credit = conv.get("credit_cost")
        acu = conv.get("acu_cost")
        if credit is not None or acu is not None:
            _add(f"- **Costs**: credit={credit}, acu={acu}")
    _add(f"- **Project**: {conv['project_path'] or '—'}")
    _add(f"- **Branch**: {conv['git_branch'] or '—'}")
    _add(f"- **Model**: {conv['model'] or '—'}")
    _add(f"- **Created**: {_fmt_ts(conv['created_at'])}")
    _add(f"- **Updated**: {_fmt_ts(conv['updated_at'])}")
    _add(f"- **Steps**: {conv['step_count']} | **Rounds**: {conv['round_count']} | **Checkpoints**: {conv['checkpoint_count']}")
    _add()
    _add("---")
    _add()

    # Build step lookup
    steps_by_index = {s["step_index"]: s for s in conv.get("steps", [])}

    # Rounds with their steps
    rounds = conv.get("rounds", [])
    if rounds:
        for rnd in rounds:
            _add(f"## Round {rnd['round_number']}")
            _add()
            prompt = (rnd["prompt"] or "").strip()
            if prompt:
                _add(f"**User prompt:**")
                _add()
                _add(prompt)
                _add()

            start = rnd["start_step"]
            end = rnd["end_step"]
            round_steps = [
                steps_by_index[i]
                for i in range(start, end + 1)
                if i in steps_by_index
            ]

            if round_steps:
                for s in round_steps:
                    vlabel = _VARIANT_LABELS.get(s["variant_field"], f"variant_{s['variant_field']}")
                    ts = _fmt_ts(s["timestamp"]) if s.get("timestamp") else ""
                    model = s.get("model") or ""
                    meta_parts = [f"step {s['step_index']}", vlabel]
                    if ts:
                        meta_parts.append(ts)
                    if model:
                        meta_parts.append(model)
                    _add(f"### {' | '.join(meta_parts)}")
                    _add()
                    text = (s["content_text"] or "").strip()
                    if text:
                        _add("```")
                        _add(text)
                        _add("```")
                    else:
                        _add("*(empty)*")
                    _add()
    else:
        # No rounds — just dump all steps
        _add("## Steps")
        _add()
        for s in conv.get("steps", []):
            vlabel = _VARIANT_LABELS.get(s["variant_field"], f"variant_{s['variant_field']}")
            ts = _fmt_ts(s["timestamp"]) if s.get("timestamp") else ""
            model = s.get("model") or ""
            meta_parts = [f"step {s['step_index']}", vlabel]
            if ts:
                meta_parts.append(ts)
            if model:
                meta_parts.append(model)
            _add(f"### {' | '.join(meta_parts)}")
            _add()
            text = (s["content_text"] or "").strip()
            if text:
                _add("```")
                _add(text)
                _add("```")
            else:
                _add("*(empty)*")
                _add()

    # Checkpoints
    checkpoints = conv.get("checkpoints", [])
    if checkpoints:
        _add("---")
        _add()
        _add("## Checkpoints")
        _add()
        for cp in checkpoints:
            _add(f"### Checkpoint at step {cp['step_index']}")
            _add()
            if cp.get("user_intent"):
                _add(f"**User intent:**")
                _add()
                _add(cp["user_intent"])
                _add()
            if cp.get("session_summary"):
                _add(f"**Session summary:**")
                _add()
                _add(cp["session_summary"])
                _add()
            if cp.get("code_change_summary"):
                _add(f"**Code changes:**")
                _add()
                _add(cp["code_change_summary"])
                _add()
            if cp.get("memory_summary"):
                _add(f"**Memory:**")
                _add()
                _add(cp["memory_summary"])
                _add()
            if cp.get("edited_files"):
                _add(f"**Edited files:**")
                _add()
                for f in cp["edited_files"].split("\n"):
                    if f.strip():
                        _add(f"- `{f.strip()}`")
                _add()

    output = "\n".join(lines)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Exported to {out_path}")
    else:
        print(output)

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show database status."""
    idx = Indexer(db_path=args.db_path)
    idx.init_schema()
    if not args.no_sync:
        idx.sync()
    status = idx.get_status()
    idx.close()

    print(f"Database:     {status['db_path']}")
    print(f"Size:         {status['db_size'] / 1024:.1f} KB")
    print(f"Conversations: {status['conversation_count']} ({status['active_count']} active, {status['archived_count']} archived)")
    print(f"Steps:         {status['step_count']}")
    print(f"Rounds:        {status['round_count']}")
    print(f"Checkpoints:   {status['checkpoint_count']}")
    # Per-source breakdown (ADR-0005).
    sources = status.get("sources") or {}
    for src in ("cascade", "devin_local"):
        s = sources.get(src)
        if not s:
            continue
        print(f"  {src:12s}: {s['conversation_count']} convs ({s['active_count']} active), "
              f"{s['step_count']} steps, {s['checkpoint_count']} checkpoints")
    return 0


def cmd_html(args: argparse.Namespace) -> int:
    """Generate HTML overview of conversations."""
    idx = Indexer(db_path=args.db_path)
    idx.init_schema()
    if not args.no_sync:
        idx.sync()
    convs = idx.list_conversations(limit=500)
    idx.close()

    if not convs:
        print("No conversations indexed.")
        return 0

    rows = []
    for c in convs:
        created = _fmt_ts(c["created_at"])
        updated = _fmt_ts(c["updated_at"])
        project = html_mod.escape(
            c["project_path"].replace("/home/julien/Sources/", "~/Sources/") if c["project_path"] else "—"
        )
        branch = html_mod.escape(c["git_branch"] or "—")
        model = html_mod.escape(c["model"] or "—")
        title = html_mod.escape(c["title"] or "—")
        created_ts = c['created_at'] if c['created_at'] else 0
        updated_ts = c['updated_at'] if c['updated_at'] else 0
        rows.append(f"""<tr>
      <td>{c['id']}</td>
      <td class="title">{title}</td>
      <td>{project}</td>
      <td>{branch}</td>
      <td>{model}</td>
      <td data-sort="{created_ts}">{created}</td>
      <td data-sort="{updated_ts}">{updated}</td>
      <td class="num">{c['step_count']}</td>
      <td class="num">{c['round_count']}</td>
      <td class="num">{c['checkpoint_count']}</td>
      <td><code>{c['cascade_id']}</code></td>
    </tr>""")

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>DCR — Conversations Overview</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; background: #f8f9fa; color: #222; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
  .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.85rem; }}
  th {{ background: #f1f3f5; font-weight: 600; position: sticky; top: 0; cursor: pointer; }}
  th:hover {{ background: #e9ecef; }}
  tr:hover {{ background: #f8f9fa; }}
  td.title {{ font-weight: 500; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; color: #666; }}
  code {{ font-size: 0.8rem; color: #888; }}
  .summary {{ display: flex; gap: 2rem; margin-bottom: 1.5rem; }}
  .stat {{ background: white; padding: 0.75rem 1.25rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .stat .val {{ font-size: 1.5rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.75rem; color: #666; text-transform: uppercase; }}
</style>
</head>
<body>
<h1>Conversations Overview</h1>
<div class="meta">Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — {len(convs)} conversations</div>
<div class="summary">
  <div class="stat"><div class="val">{len(convs)}</div><div class="label">Conversations</div></div>
  <div class="stat"><div class="val">{sum(c['step_count'] for c in convs)}</div><div class="label">Steps</div></div>
  <div class="stat"><div class="val">{sum(c['round_count'] for c in convs)}</div><div class="label">Rounds</div></div>
  <div class="stat"><div class="val">{len(set(c['project_path'] for c in convs if c['project_path']))}</div><div class="label">Projects</div></div>
</div>
<table>
<thead><tr>
  <th>ID</th><th>Title</th><th>Project</th><th>Branch</th><th>Model</th>
  <th>Created</th><th>Updated</th><th>Steps</th><th>Rounds</th><th>CPs</th><th>Cascade</th>
</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
<script>
  document.querySelectorAll('th').forEach((th, i) => {{
    th.onclick = () => {{
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const dir = th.dataset.dir === 'asc' ? -1 : 1;
      th.dataset.dir = dir === 1 ? 'asc' : 'desc';
      rows.sort((a, b) => {{
        const ca = a.children[i].getAttribute('data-sort');
        const cb = b.children[i].getAttribute('data-sort');
        if (ca !== null && cb !== null) {{
          return (parseFloat(ca) - parseFloat(cb)) * dir;
        }}
        const va = a.children[i].textContent.trim();
        const vb = b.children[i].textContent.trim();
        const na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
        return va.localeCompare(vb) * dir;
      }});
      rows.forEach(r => tbody.appendChild(r));
    }};
  }});
</script>
</body>
</html>"""

    out_path = Path(args.output) if args.output else DEFAULT_DB_PATH.parent / "conversations.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"HTML overview written to {out_path}")
    print(f"Open with: file://{out_path}")
    return 0


# --- Main ---


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="dcr",
        description="Devin Conversations Retriever — search Cascade & Devin Local conversations",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default=None,
        help="Path to SQLite database (default: ~/.local/share/dcr/dcr.db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync database with Cascade .pb files and Devin Local sessions.db")
    p_sync.set_defaults(func=cmd_sync)

    # search
    p_search = subparsers.add_parser("search", help="Full-text search conversations")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-l", "--limit", type=int, default=20, help="Max results (default: 20)")
    p_search.add_argument("-p", "--project", default=None, help="Filter by project path (exact or prefix)")
    p_search.add_argument("--date-from", dest="date_from", type=_parse_date, default=None,
                          help="Only conversations created after this date (YYYY-MM-DD)")
    p_search.add_argument("--date-to", dest="date_to", type=_parse_date, default=None,
                          help="Only conversations created before this date (YYYY-MM-DD)")
    p_search.add_argument("-s", "--source", default=None, choices=["rounds", "steps", "checkpoints"],
                          help="Restrict search to one table")
    p_search.add_argument("--no-sync", action="store_true", help="Skip auto-sync before search")
    p_search.set_defaults(func=cmd_search)

    # list
    p_list = subparsers.add_parser("list", help="List indexed conversations")
    p_list.add_argument("-l", "--limit", type=int, default=50, help="Max conversations (default: 50)")
    p_list.add_argument("-p", "--project", default=None, help="Filter by project path (exact or prefix)")
    p_list.add_argument("--no-sync", action="store_true", help="Skip auto-sync before listing")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser("show", help="Show a specific conversation")
    p_show.add_argument("cascade_id", help="Cascade UUID, prefix, or numeric DB id")
    p_show.add_argument("--steps", type=int, default=20, help="Max steps to display (default: 20)")
    p_show.add_argument("--no-sync", action="store_true", help="Skip auto-sync before showing")
    p_show.set_defaults(func=cmd_show)

    # export
    p_export = subparsers.add_parser("export", help="Export a conversation as structured markdown")
    p_export.add_argument("cascade_id", help="Cascade UUID, prefix, or numeric DB id")
    p_export.add_argument("-o", "--output", default=None, help="Output file path (default: stdout)")
    p_export.add_argument("--no-sync", action="store_true", help="Skip auto-sync before exporting")
    p_export.set_defaults(func=cmd_export)

    # status
    p_status = subparsers.add_parser("status", help="Show database status")
    p_status.add_argument("--no-sync", action="store_true", help="Skip auto-sync before showing status")
    p_status.set_defaults(func=cmd_status)

    # html
    p_html = subparsers.add_parser("html", help="Generate HTML overview")
    p_html.add_argument("-o", "--output", default=None, help="Output file path")
    p_html.add_argument("--no-sync", action="store_true", help="Skip auto-sync before generating")
    p_html.set_defaults(func=cmd_html)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Resolve cascade_id for show/export commands
    if args.command in ("show", "export"):
        idx = Indexer(db_path=args.db_path)
        idx.init_schema()
        if not args.no_sync:
            idx.sync()
        # Try numeric DB id first
        if args.cascade_id.isdigit():
            conv = idx.get_conversation_by_db_id(int(args.cascade_id))
            if conv:
                args.cascade_id = conv["cascade_id"]
                idx.close()
            else:
                idx.close()
                print(f"Conversation with DB id '{args.cascade_id}' not found.")
                return 1
        elif not idx.get_conversation(args.cascade_id):
            # Try prefix match on cascade_id
            cur = idx.conn.execute(
                "SELECT cascade_id FROM conversations WHERE cascade_id LIKE ?",
                (args.cascade_id + "%",),
            )
            row = cur.fetchone()
            idx.close()
            if row:
                args.cascade_id = row[0]

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

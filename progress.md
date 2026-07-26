# progress.md — Living Status Board

> Last updated: 2026-07-26 (session 4 — export command)

## Current Phase: Core Complete (M2–M6)

M2–M6 complete. M7 (MCP server) deferred. All docs and README up to date.

## Milestones

| # | Milestone | Status | Notes |
|---|---|---|---|
| M1 | Project documentation & structure | Completed | 2026-07-24 — AGENTS.md, docs, progress.md, architecture, 3 ADRs, .devin/ config, pyproject.toml |
| M2 | Decryption module (`decrypt.py`) + tests | Completed | 2026-07-26 — 3 functions (decrypt_bytes, decrypt_file, decrypt_batch), 10 tests, validated on real .pb |
| M3 | Protobuf parser (`parser.py`) + tests | Completed | 2026-07-26 — wire-format parser, 4 dataclasses, text extraction, round grouping, 23 tests, validated on real .bin |
| M4 | SQLite FTS5 indexer (`indexer.py`) + tests | Completed | 2026-07-26 — 4 tables + 3 FTS5 + 9 triggers, enriched fields (project, branch, model, timestamps, title), sync() for incremental updates, 32 tests, validated on real .pb |
| M5 | Search engine (`search.py`) + tests | Completed | 2026-07-26 — FTS5 BM25 search, filters (project, date, source_table), snippets, auto-sync, search_conversations dedup, 24 tests |
| M6 | CLI interface (`dcr`) + tests | Completed | 2026-07-26 — 7 subcommands (sync, search, list, show, export, status, html), auto-sync, prefix resolution, 25 tests |
| M7 | MCP server (`server.py`) + tests | Deferred | MCP vs skill : decision reportee par l'utilisateur |

> Tests are integrated into each milestone (M2–M7), not a separate milestone.

## What's Done

- [x] Research: evaluated existing projects (windsurf-decrypt, lore, deja, RepoChatMCP, cursor-chat-history-mcp)
- [x] Research: confirmed no existing MCP server for Windsurf `.pb` search
- [x] Research: vibe coding project management best practices
- [x] Research: MCP server design guidelines (Python SDK, FastMCP)
- [x] Validated: decryption works on local `.pb` files (tested on `155522f6...`)
- [x] Validated: Markdown export produces complete conversation archives
- [x] Validated: `trajectory_search` content matches decrypted content
- [x] Created: `AGENTS.md` (root)
- [x] Created: `docs/index.md`
- [x] Created: `progress.md` (this file)
- [x] Created: `docs/architecture.md` — 6 modules, data flow, schemas, perfs
- [x] Created: `docs/decisions/` — 3 ADRs (Python+MCP, SQLite FTS5, reuse decrypt tools)
- [x] Created: `.devin/AGENTS.md` — Cascade config
- [x] Created: `.devin/skills/cascade-self-config/references/` — project-tooling.md, diagnostic-catalog.md
- [x] Created: `pyproject.toml` — dependencies, scripts
- [x] Created: `.gitignore` — artifacts, venv, DB
- [x] Git init + initial commit (e38f42d)
- [x] Auto-config: 3 rules (update-docs, definition-of-done, test-with-code)
- [x] Auto-config: 1 workflow (/end-session)
- [x] M2: `src/dcr/decrypt.py` — AES-256-GCM decryption (decrypt_bytes, decrypt_file, decrypt_batch)
- [x] M2: `tests/test_decrypt.py` — 10 tests (5 nominal, 5 error), all passing
- [x] M2: Validated on real .pb file (04a36d38... → 499KB plaintext)
- [x] M2: Dependencies installed (mcp, pydantic, pytest via `pip install -e ".[dev]"`)
- [x] M3: `src/dcr/parser.py` — wire-format parser (read_varint, iter_fields, parse_trajectory, parse_step, parse_checkpoint, group_rounds, extract_step_text)
- [x] M3: 4 dataclasses (TrajectoryInfo, StepInfo, CheckpointInfo, RoundInfo)
- [x] M3: `tests/test_parser.py` — 23 tests (synthetic + real data), all passing
- [x] M3: Validated on real .pb file (04a36d38... → 20 steps, 1 round, 2 checkpoints, variant distribution extracted)
- [x] M4: `src/dcr/indexer.py` — Indexer class with schema (4 tables + 3 FTS5 + 9 triggers), index_trajectory, index_file, index_directory (incremental), get_status, list_conversations, get_conversation
- [x] M4: `tests/test_indexer.py` — 24 tests (schema, CRUD, FTS5 search, incremental, real data), all passing
- [x] M4: Validated on real .pb files (index_file + index_directory with incremental skip)
- [x] Fields update: Added project_path, git_branch, model, created_at, updated_at to parser + indexer
- [x] Fields update: Added timestamp, model to StepInfo and steps table
- [x] Fields update: Title derivation from checkpoint user_intent first line (Windsurf pattern)
- [x] Fields update: Updated docs/architecture.md with new schema
- [x] Fields update: Re-indexed 50 conversations with enriched fields (titles, dates, projects, branches, models)
- [x] Sync: Added `sync()` method — detects new/modified/deleted .pb files, uses DEFAULT_CASCADE_DIR
- [x] Sync: 8 new tests (new, unchanged, modified, stale deletion, stale keep, new file detection, default dir, real data)
- [x] HTML overview: `conversations.html` generated at `~/.local/share/dcr/`
- [x] M5: `src/dcr/search.py` — SearchEngine class with FTS5 BM25 search across rounds/steps/checkpoints
- [x] M5: Filters: project (exact + prefix), date_from/date_to, source_table restriction
- [x] M5: Snippet extraction with >>> <<< markers, FTS5 query escaping
- [x] M5: search_conversations() — deduplicated one-per-conversation results
- [x] M5: Auto-sync before search (configurable via auto_sync param)
- [x] M5: `tests/test_search.py` — 24 tests (basic, filters, source table, dedup, auto-sync, escaping, real data)
- [x] M6: `src/dcr/cli.py` — argparse CLI with 7 subcommands (sync, search, list, show, export, status, html)
- [x] M6: Auto-sync before search/list/html (configurable via --no-sync)
- [x] M6: Cascade ID prefix resolution for show command
- [x] M6: HTML generation with sortable table
- [x] M6: Entry point `dcr` declared in pyproject.toml
- [x] M6: `tests/test_cli.py` — 25 tests (all subcommands, filters, prefix, export, empty DB, real data)

## What's In Progress

Nothing currently in progress. M7 (MCP server) is deferred per user decision.

## What's Blocked

Nothing currently blocked.

## AI Handoff Notes

If you're picking up this project in a new session:

1. Read `AGENTS.md` first for project overview
2. Read this file (`progress.md`) for current state
3. Read `docs/architecture.md` for technical design
4. Check `docs/decisions/` for rationale on design choices
5. The `.venv` has all dependencies installed (`pip install -e ".[dev]"` — mcp, cryptography, protobuf, pydantic, pytest)
6. `src/dcr/decrypt.py` is done — use `from dcr.decrypt import decrypt_file` to decrypt .pb files
7. `src/dcr/parser.py` is done — use `from dcr.parser import parse, parse_file` to parse decrypted protobuf
8. `src/dcr/indexer.py` is done — use `from dcr.indexer import Indexer` to store/search conversations in SQLite. `sync()` auto-detects new/modified/deleted .pb files.
9. A test conversation is already decrypted at `artifacts/decrypted/155522f6.bin`
10. Markdown export is at `artifacts/markdown/155522f6/` (31 rounds, 697 steps)
11. `/tmp/windsurf-decrypt/` is gone (ephemeral) — reference code is in git history and in `src/dcr/`
12. Source repo for reference: https://github.com/dayearleo/windsurf-local-user-data-decryption (MIT)
13. DB location: `~/.local/share/dcr/dcr.db` — 50 conversations, 9161 steps, 499 rounds, 164 checkpoints
14. HTML overview: `~/.local/share/dcr/conversations.html`
15. Next step: M7 — MCP server (deferred per user decision — MCP vs skill discussion pending)
16. Total tests: 114 (10 decrypt + 23 parser + 32 indexer + 24 search + 25 CLI), all passing
17. CLI usage: `dcr sync`, `dcr search <query>`, `dcr list`, `dcr show <cascade_id>`, `dcr export <cascade_id> [-o file]`, `dcr status`, `dcr html`

## Bug History

| # | Date | Description | Fix | File |
|---|---|---|---|---|
| B1 | 2026-07-26 | HTML overview: sorting by date columns didn't work (`parseFloat("2026-07-25")` returned `2026`, all dates sorted equally) | Added `data-sort` attribute with raw Unix timestamp on date `<td>` elements; JS sort logic checks `data-sort` first | `src/dcr/cli.py` |

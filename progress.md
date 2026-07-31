# progress.md — Living Status Board

> Last updated: 2026-07-31 (M8 Phase 2 completed — enrichment, 191 tests passing)

## Current Phase: M8 Phase 2 Completed — Enrichment

M2–M6 complete. M7 (MCP server) rejected (ADR-0004). **M8 Phase 1A (Devin Local MVP) completed** — `devin_local.py`, unified schema, `sync()` auto-dispatch. **M8 Phase 2 (enrichment) completed 2026-07-31** — dedicated `tool_calls` table + FTS5 (join `chat_message.tool_calls` + tool-role nodes via `tool_call_id`), `dcr search --source-type` filter, `dcr list --source-type` filter, `dcr show` displays thinking/tool_calls with enrichment flags, `dcr show --full-tree` renders lateral branches, `dcr export` renders thinking in collapsible `<details>` + tool calls with arguments. 14 new tests (191 total). Phase 1B **annulée** (Cascade abandonné).

## Milestones

| # | Milestone | Status | Notes |
|---|---|---|---|
| M1 | Project documentation & structure | Completed | 2026-07-24 — AGENTS.md, docs, progress.md, architecture, 3 ADRs, .devin/ config, pyproject.toml |
| M2 | Decryption module (`decrypt.py`) + tests | Completed | 2026-07-26 — 3 functions (decrypt_bytes, decrypt_file, decrypt_batch), 10 tests, validated on real .pb |
| M3 | Protobuf parser (`parser.py`) + tests | Completed | 2026-07-26 — wire-format parser, 4 dataclasses, text extraction, round grouping, 23 tests, validated on real .bin |
| M4 | SQLite FTS5 indexer (`indexer.py`) + tests | Completed | 2026-07-26 — 4 tables + 3 FTS5 + 9 triggers, enriched fields (project, branch, model, timestamps, title), sync() for incremental updates, 32 tests, validated on real .pb |
| M5 | Search engine (`search.py`) + tests | Completed | 2026-07-26 — FTS5 BM25 search, filters (project, date, source_table), snippets, auto-sync, search_conversations dedup, 24 tests |
| M6 | CLI interface (`dcr`) + tests | Completed | 2026-07-26 — 7 subcommands (sync, search, list, show, export, status, html), auto-sync, prefix resolution, numeric DB id, --project filter on list, 31 tests |
| M7 | MCP server (`server.py`) + tests | Rejected | CLI over MCP — voir ADR-0004. Coût token permanent pour usage occasionnel, 0/9 critères favorables au MCP |
| M8 | Devin Local integration (Phase 1A) + Cascade enrichment (Phase 1B, cancelled) + Enrichment (Phase 2) | Phase 1A + Phase 2 Completed | 2026-07-31 — Phase 1A: `devin_local.py`, schéma unifié, sync() auto-dispatch, 53 tests. Phase 2: `tool_calls` table + FTS5, `--source-type` filter (search+list), `--full-tree` (show+export), thinking in `<details>`, tool_calls display, 14 tests (191 total). Phase 1B **annulée**. Phases 3-4: résilience schema, skill @conversation |

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
- [x] M6: `tests/test_cli.py` — 31 tests (all subcommands, filters, prefix, numeric DB id, export, empty DB, real data)
- [x] M6 fix: `dcr list -p/--project` filter (exact + prefix match on project_path)
- [x] M6 fix: `dcr show/export` accept numeric DB id (resolves to cascade_id internally)
- [x] M6 fix: `Indexer.list_conversations(project=)` and `Indexer.get_conversation_by_db_id()` added

## What's In Progress

Nothing currently in progress. M8 Phase 2 completed. Phase 3 (schema resilience) and Phase 4 (`@conversation` skill) pending — awaiting user decision.

## What's Blocked

Nothing currently blocked.

## M8 — Devin Local Integration (planned)

**Decision**: ADR-0005 (revised 2026-07-31 after verifying real `sessions.db`) — unified schema with `source_type` discriminator + full-tree indexing. See `docs/decisions/0005-unified-schema-devin-local.md` for full rationale.

> **Schema reality check** (verified 2026-07-31 against `~/.local/share/devin/cli/sessions.db`):
> 102 sessions, 6056 `message_nodes`. `message_nodes` has NO SQL columns `role`/`content`/`thinking`/`tool_calls` — those are keys inside the `chat_message` JSON string. `sessions.metadata` has `total_credit_cost`/`total_acu_cost` (NOT `token_input/output/cached`). `agent_mode` values: `normal`/`accept-edits`/`bypass`/`''`. `node_id` is NOT chronological (3705 inversions on 466 nodes) — order by `created_at`. 62 % of nodes are off main chain (lateral branches: regenerations, edited prompts).

### Phase 1A: Devin Local MVP — full-tree indexing (priority)

Small, self-contained. Does NOT touch the Cascade parser — zero risk to the 124 existing tests. `thinking`/`tool_calls` captured for free from `chat_message` JSON keys.

| Task | Module | Status |
|---|---|---|
| 1A.1 | `devin_local.py` (new) — SQLite reader: `sessions.db` → `TrajectoryInfo`. Full-tree (all nodes), `json.loads(chat_message)`, `on_main_chain` via tip→root walk, compaction → `checkpoints` | Done |
| 1A.2 | `indexer.py` — schema migration: `source_type`, `agent_mode`, `credit_cost`, `acu_cost` (conversations) + `role`, `thinking`, `tool_calls_json`, `tool_call_id`, `node_id`, `parent_node_id`, `on_main_chain` (steps). Idempotent `ALTER TABLE` | Done |
| 1A.3 | `indexer.py` — `sync()` auto-dispatch to `_sync_cascade()` + `_sync_devin_local()` | Done |
| 1A.4 | `indexer.py` — `_sync_devin_local()`: incremental on `last_activity_at`, archive deleted, `mode=ro` | Done |
| 1A.5 | `cli.py` — `dcr status` shows both sources, `dcr list` shows `source_type` | Done |
| 1A.6 | `tests/` — `test_devin_local.py` (32 tests), `test_indexer_devin_local.py` (21 tests) — full-tree, compaction, main-chain flag, incremental, archive, schema migration, FTS5 search | Done |
| 1A.7 | `docs/` — ADR-0005 + architecture.md + progress.md + index.md | Done |

### Phase 1B: Cascade parser enrichment (CANCELLED 2026-07-31)

**Annulé** — Cascade va être abandonné dans Devin Desktop, Devin Local sera bientôt la seule source. Enrichir le parser Cascade n'a pas d'intérêt : les conversations existantes restent recherchables (texte déjà indexé), et le diagnostic `cascade-self-config` porte désormais sur Devin Local (où thinking/tool_calls sont déjà capturés gratuitement en Phase 1A). Le code Cascade (`decrypt.py`, `parser.py`, `_sync_cascade`) reste en place pour l'archive — il n'est juste plus enrichi.

| Task | Module | Status |
|---|---|---|
| 1B.1 | `parser.py` — enrich Cascade extraction: thinking (field 3), tool_calls (field 7), command (field 23), result (field 24) | Cancelled |
| 1B.2 | `cli.py` — add `dcr sync --force` flag (does not exist yet) to bypass mtime+size incremental skip | Cancelled |
| 1B.3 | `tests/` — parser enrichment tests + `--force` flag tests | Cancelled |

### Phase 2: Enrichment — exploit structured data (completed 2026-07-31)

| Task | Status |
|---|---|
| 2.1 Dedicated `tool_calls` table + FTS5 (join `chat_message.tool_calls` + tool-role nodes via `tool_call_id`) | Done |
| 2.2 `dcr export` renders thinking in collapsible `<details>` + tool calls with arguments | Done |
| 2.3 `dcr search --source-type cascade\|devin_local` filter + `dcr list --source-type` filter | Done |
| 2.4 `dcr show` displays tool calls summary + thinking/tool_calls enrichment flags (`{T}`, `{C}`) | Done |
| 2.5 `dcr show --full-tree` + `dcr export --full-tree`: render lateral branches (`on_main_chain=0`), default = main chain only | Done |

### Phase 3: Resilience — track Devin Local evolution

| Task | Status |
|---|---|
| 3.1 `dcr status` displays detected vs supported schema version | Pending |
| 3.2 `scripts/check_devin_schema.py` | Pending |
| 3.3 CI test: `test_schema_compat.py` | Pending |
| 3.4 ADR-0006: compatibility strategy | Pending |

### Phase 4: `@conversation` skill (recover lost Cascade feature)

| Task | Status |
|---|---|
| 4.1 Skill `.devin/skills/dcr-conversation/SKILL.md` | Pending |
| 4.2 Global rule update | Pending |

## AI Handoff Notes

If you're picking up this project in a new session:

1. Read `AGENTS.md` first for project overview
2. Read this file (`progress.md`) for current state
3. Read `docs/architecture.md` for technical design
4. Check `docs/decisions/` for rationale on design choices
5. The `.venv` has all dependencies installed (`pip install -e ".[dev]"` — mcp, cryptography, protobuf, pydantic, pytest)
6. `src/dcr/decrypt.py` is done — use `from dcr.decrypt import decrypt_file` to decrypt .pb files
7. `src/dcr/parser.py` is done — use `from dcr.parser import parse, parse_file` to parse decrypted protobuf
8. `src/dcr/indexer.py` is done — use `from dcr.indexer import Indexer` to store/search conversations in SQLite. `sync()` auto-detects **both** sources (Cascade `.pb` + Devin Local `sessions.db`) and **archives** (never deletes) conversations whose source disappeared.
9. A test conversation is already decrypted at `artifacts/decrypted/155522f6.bin`
10. Markdown export is at `artifacts/markdown/155522f6/` (31 rounds, 697 steps)
11. `/tmp/windsurf-decrypt/` is gone (ephemeral) — reference code is in git history and in `src/dcr/`
12. Source repo for reference: https://github.com/dayearleo/windsurf-local-user-data-decryption (MIT)
13. DB location: `~/.local/share/dcr/dcr.db` — 216 conversations (112 cascade + 104 devin_local), 25917 steps, 1141 rounds, 3075 checkpoints
14. HTML overview: `~/.local/share/dcr/conversations.html`
15. **M8 Phase 1A completed** — `devin_local.py` reader (full-tree, `on_main_chain`, compaction checkpoints), unified schema (`source_type` + tree columns), `sync()` auto-dispatch, CLI per-source display. See M8 section above and `docs/decisions/0005-unified-schema-devin-local.md`.
16. Total tests: 191 (10 decrypt + 23 parser + 38 indexer + 26 search + 36 CLI + 32 devin_local + 27 indexer_devin_local), all passing
17. CLI usage: `dcr sync`, `dcr search <query>`, `dcr list [-p <project>]`, `dcr show <id_or_uuid>`, `dcr export <id_or_uuid> [-o file]`, `dcr status`, `dcr html`
18. **Devin Local source**: `~/.local/share/devin/cli/sessions.db` — SQLite plaintext, 104 sessions, 6575 message_nodes, schema version 16 (refinery migrations). No encryption. Opened in `mode=ro`. Full-tree indexing (all nodes incl. lateral branches), `on_main_chain` via tip→root walk, `thinking`/`tool_calls` captured from `chat_message` JSON.
19. **Cascade source**: `~/.codeium/windsurf/cascade/*.pb` — encrypted protobuf, last file 2026-07-29. Parser currently discards thinking (field 3) and tool_calls (field 7) — **enrichissement annulé (Phase 1B)**, Cascade va être abandonné. Le code reste pour l'archive.
20. **Next steps**: Phase 3 (schema resilience — `dcr status` schema version, `check_devin_schema.py`, CI compat test, ADR-0006), Phase 4 (`@conversation` skill). Phase 1B annulée, Phase 2 completed.

## Bug History

| # | Date | Description | Fix | File |
|---|---|---|---|---|
| B1 | 2026-07-26 | HTML overview: sorting by date columns didn't work (`parseFloat("2026-07-25")` returned `2026`, all dates sorted equally) | Added `data-sort` attribute with raw Unix timestamp on date `<td>` elements; JS sort logic checks `data-sort` first | `src/dcr/cli.py` |
| B2 | 2026-07-26 | **Perte de données** : `sync()` supprimait les conversations dont le .pb n'existait plus sur le disque (`remove_stale=True` par défaut). L'auto-sync avant chaque recherche déclenchait cette suppression. | Ajout colonnes `archived` + `archived_at` au schéma. `sync()` fait maintenant un `UPDATE archived=1` au lieu de `DELETE`. Le paramètre `remove_stale` est déprécié (ignoré). Migration automatique des BDD existantes via `ALTER TABLE`. | `src/dcr/indexer.py` |
| B3 | 2026-07-26 | **Migration cassée** : `CREATE INDEX idx_conversations_archived ON conversations(archived)` dans `SCHEMA_SQL` s'exécutait avant les `ALTER TABLE` de `MIGRATION_SQL`, échouant sur les DB existantes sans la colonne `archived`. | Déplacé la création de l'index `idx_conversations_archived` de `SCHEMA_SQL` vers `MIGRATION_SQL` (après les `ALTER TABLE`). | `src/dcr/indexer.py` |
| B4 | 2026-07-26 | **IDs numériques non stables** : `index_trajectory` utilisait `DELETE` + `INSERT` pour l'upsert, ce qui changeait l'ID autoincrement à chaque re-index. Conséquence : `dcr show 145` échouait après un sync car l'ID devenait 147. Cascade tentait alors `trajectory_search` avec l'ID numérique (qui attend un UUID) → échec. | Remplacé `DELETE` + `INSERT` par `SELECT` + `UPDATE` (préserve l'ID) ou `INSERT` (si nouveau). Les lignes enfants (rounds, steps, checkpoints) sont supprimées et ré-insérées manuellement. Test de régression `test_index_trajectory_id_stable_across_reindex` ajouté. | `src/dcr/indexer.py` |

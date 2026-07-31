# Architecture — Devin Conversations Retriever

> Last updated: 2026-07-31 (M8 Phase 1A completed — Devin Local integration live)

## Overview

```
~/.codeium/windsurf/cascade/*.pb     ~/.local/share/devin/cli/sessions.db
        │                                       │
        ▼                                       │
  ┌─────────────┐                               │
  │  decrypt.py  │  AES-256-GCM decryption       │
  │              │  Key: safeCodeiumworldKeYsecretBalloon
  └──────┬───────┘                               │
         │ plaintext protobuf bytes               │
         ▼                                       │
  ┌─────────────┐                               │
  │  parser.py   │  Protobuf wire-format parsing │
  │  (enriched)  │  CortexTrajectory → steps     │
  │              │  + thinking + tool_calls       │
  └──────┬───────┘                               │
         │ TrajectoryInfo (enriched)             │
         │                                       │
         │              ┌────────────────────┐   │
         │              │  devin_local.py     │   │
         │              │  (new module)       │   │
         │              │  SQLite reader      │◄──┘
         │              │  sessions.db →      │
         │              │  TrajectoryInfo     │
         │              └─────────┬──────────┘   │
         │                        │              │
         ▼                        ▼              │
  ┌─────────────────────────────────────────┐    │
  │  indexer.py  — unified schema            │    │
  │  source_type: 'cascade' | 'devin_local'  │    │
  │  conversations (+agent_mode, +costs)     │    │
  │  steps (+role, +thinking, +tool_calls)   │    │
  │  rounds | checkpoints                     │    │
  │  sync(): auto-detects both sources        │    │
  │  missing source → archive (never delete)  │    │
  └──────┬──────────────────────────────────┘    │
         │ reads from DB ◄────────────────────────┘
         ▼
  ┌─────────────┐
  │  search.py   │  FTS5 full-text search (BM25)
  │              │  filters: project, date, source_table
  │              │  auto-sync before search (archives stale)
  └──────┬───────┘
         │ search results
         ▼
  ┌─────────────┐
  │  cli.py      │  Command-line interface
  │              │  sync, search, list, show, export, status, html
  └─────────────┘
```

> **Key principle**: The SQLite database is a **permanent archive**. Once a conversation
> is indexed, it is never deleted — even if the source file is removed. Conversations whose
> source disappears are marked `archived=1` but remain fully searchable. This applies to
> **both** Cascade (`.pb` files) and Devin Local (`sessions.db` entries).

## Modules

### `decrypt.py` — Decryption

- **Source**: Adapted from `windsurf-local-user-data-decryption/tools/decrypt_pb.py`
- **Input**: `.pb` file path
- **Output**: Raw protobuf bytes
- **Algorithm**: AES-256-GCM, key = `safeCodeiumworldKeYsecretBalloon`
- **File format**: `[nonce 12B][ciphertext][GCM tag 16B]`

### `parser.py` — Protobuf Parsing (enrichment cancelled — Phase 1B)

- **Source**: Adapted from `windsurf-local-user-data-decryption/tools/scan_trajectory.py`
- **Input**: Decrypted protobuf bytes
- **Output**: Structured `TrajectoryInfo` with:
  - `trajectory_id`: UUID (top-level field 1)
  - `cascade_id`: UUID (top-level field 6, filename stem)
  - `project_path`: Project directory (top-level field 7 → field 1 → field 1, stripped of `file://` prefix)
  - `git_branch`: Git branch name (top-level field 7 → field 1 → field 4)
  - `model`: AI model name (step metadata field 28, e.g. `glm-5-2`)
  - `created_at`: Timestamp of first step (Unix epoch seconds)
  - `updated_at`: Timestamp of last step
  - `title`: Derived from checkpoint `user_intent` first line, fallback to first user prompt
  - `steps`: List of `StepInfo` with `type`, `status`, `variant_field`, `variant_data`, `content_text`, `timestamp`, `model`, **`thinking`**, **`tool_calls_json`**, **`role`** (enriched — see ADR-0005)
  - `checkpoints`: List of `CheckpointInfo` with summaries, edited files, plan snapshots
  - `rounds`: List of `RoundInfo` grouping steps by user input cycles
- **Key variant_fields**:
  - `19` = user_input (user's prompt)
  - `20` = planner_response (field 1 = visible text, field 3 = thinking, field 7 = tool_calls, field 8 = visible text)
  - `28` = run_command (field 23 = command, field 24 = output, field 28 = shell)
  - `30` = checkpoint (compression summary)
  - `37` = command_result (field 24 = output)
- **Enrichment (ADR-0005, Phase 1B — deferred)**: The current parser extracts only `content_text` via naive string extraction. The `.pb` files already contain structured data (thinking in field 3, tool calls in field 7, command strings in field 23, outputs in field 24) that is currently **discarded**. Enriching the parser recovers this data retroactively — a re-index (`dcr sync --force`, new flag) of existing `.pb` files populates `thinking` and `tool_calls_json` for all past Cascade conversations. **Deferred to Phase 1B** (orthogonal to Devin Local MVP; Devin Local captures these fields for free in Phase 1A via JSON keys).
- **Title derivation logic**:
  1. `conversation_title` from any checkpoint (field 10) — usually empty
  2. First line of `user_intent` from first checkpoint (field 4) — e.g. "Merge Conflict Resolution\n..."
  3. First user prompt truncated to 80 chars
  4. `cascade_id` or `trajectory_id` as last resort

### `devin_local.py` — Devin Local SQLite Reader (completed — ADR-0005 Phase 1A)

- **Status**: Completed (M8 / Phase 1A.1)
- **Input**: `~/.local/share/devin/cli/sessions.db` (opened in `mode=ro`)
- **Output**: List of `TrajectoryInfo` (reuses existing dataclasses from `parser.py`)
- **Schema**: Devin Local uses `refinery` migrations (16 versions, additive). Tables: `sessions`, `message_nodes` (forest with compaction), `tool_call_state` (533 rows), `prompt_history`.
- **Critical**: `message_nodes` has NO SQL columns `role`/`content`/`thinking`/`tool_calls` — those are **keys inside the `chat_message` JSON string**. SQL columns are: `row_id, session_id, node_id, parent_node_id, chat_message (JSON), created_at, metadata (JSON)`. `devin_local.py` must `json.loads(chat_message)` per node.
- **Mapping** (see ADR-0005 for full table):
  - `sessions.id` (slug) → `cascade_id` (universal ID)
  - `message_nodes` (**full tree**, all nodes) → `steps`, ordered by `created_at ASC, node_id ASC` (`node_id` is NOT chronological — 3705 inversions on a 466-node session)
  - `chat_message.role` (user/assistant/system/tool) → `variant_field` + `role` column
  - `chat_message.thinking.thinking` (nested object) → `StepInfo.thinking`
  - `chat_message.tool_calls` (JSON array) → `StepInfo.tool_calls_json`
  - `chat_message.tool_call_id` → `StepInfo.tool_call_id` (tool-role nodes only)
  - `node_id`, `parent_node_id` → new `steps` columns (preserve forest structure)
  - `on_main_chain` (computed via tip→root walk on `sessions.main_chain_id`) → new `steps` column (0/1)
  - `metadata.extensions["compact/prior_node_ids"]` → `checkpoints` (session_summary = compaction node's content)
  - `sessions.metadata.total_credit_cost` → `credit_cost`; `sessions.metadata.total_acu_cost` → `acu_cost` (NO token_input/output/cached — they don't exist at session level)
- **Full-tree rationale**: 62 % of nodes are lateral branches (regenerations, edited prompts) — valuable signal for `cascade-self-config` diagnosis. `on_main_chain` flag keeps default `dcr show` lean; `dcr show --full-tree` (Phase 2.5) surfaces branches.
- **Schema versioning**: reads `refinery_schema_history` — warns on unknown versions, degrades gracefully (additive schema).

### `indexer.py` — SQLite + FTS5 Indexing (unified schema — ADR-0005)

- **Database**: `~/.local/share/dcr/dcr.db` (or configurable)
- **Tables**:
  - `conversations`: id, cascade_id, trajectory_id, title, trajectory_type, source, project_path, git_branch, model, created_at, updated_at, step_count, round_count, checkpoint_count, pb_mtime, pb_size, archived, archived_at, indexed_at, **`source_type`** ('cascade'|'devin_local'), **`agent_mode`** (verified: normal/accept-edits/bypass/''), **`credit_cost`**, **`acu_cost`**
  - `rounds`: id, conversation_id, round_number, prompt, start_step, end_step
  - `steps`: id, conversation_id, step_index, type, status, variant_field, content_text, timestamp, model, **`role`** (user/assistant/system/tool), **`thinking`**, **`tool_calls_json`**, **`tool_call_id`**, **`node_id`** (Devin Local), **`parent_node_id`** (Devin Local), **`on_main_chain`** (0/1, Devin Local)
  - `checkpoints`: id, conversation_id, step_index, checkpoint_index, user_intent, session_summary, code_change_summary, memory_summary, conversation_title, plan_snapshot, intent_only, included_step_index_start, included_step_index_end, edited_files
- **FTS5 virtual tables**: `rounds_fts` (prompt), `steps_fts` (content_text), `checkpoints_fts` (user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
- **Triggers**: 9 auto-sync triggers (insert/delete/update on each FTS5 table)
- **Indexes**: cascade_id, project_path, created_at, archived, source_type, conversation_id (rounds/steps/checkpoints)
- **Migrations**: `MIGRATION_SQL` list — `ALTER TABLE` statements run after `SCHEMA_SQL`, with `try/except` for idempotency. ADR-0005 columns added here (source_type, agent_mode, credit_cost, acu_cost, role, thinking, tool_calls_json, tool_call_id, node_id, parent_node_id, on_main_chain).
- **Indexing strategy — Cascade**: Incremental — skip files where mtime + size match existing record. Conversations whose `.pb` file no longer exists are **archived** (archived=1), never deleted. (Cascade parser enrichment deferred to Phase 1B — see ADR-0005 D5.)
- **Indexing strategy — Devin Local**: Incremental on `sessions.last_activity_at`. **Full-tree** indexing (all `message_nodes`, not just main chain). Sessions absent from `sessions.db` are **archived** (same principle — never delete). Opened in `mode=ro` to avoid lock contention.
- **sync()**: Auto-detects both sources (`~/.codeium/windsurf/cascade/*.pb` + `~/.local/share/devin/cli/sessions.db`). Missing source = silent skip. Dispatches to `_sync_cascade()` + `_sync_devin_local()`.

### `search.py` — Search Engine

- **Query type**: FTS5 full-text (BM25 ranking)
- **Tables searched**: `rounds_fts`, `steps_fts`, `checkpoints_fts` (all by default, or restrict via `source_table`)
- **Filters**: `project` (exact + prefix match), `date_from`/`date_to` (on `created_at`), `source_table` (rounds/steps/checkpoints)
- **Snippets**: FTS5 `snippet()` with `>>>match<<<` markers, 20-word window
- **Query escaping**: Tokens wrapped in double quotes to prevent FTS5 syntax injection; `AND`/`OR`/`NOT` preserved
- **Deduplication**: `search_conversations()` returns one result per conversation (best match)
- **Auto-sync**: Calls `sync()` before search if `auto_sync=True` (default)
- **Result format**: `SearchResult` dataclass with conversation metadata, source table, snippet, score
- **Limit**: Configurable, default 50

### `cli.py` — Command-Line Interface

- **Entry point**: `dcr` (declared in `pyproject.toml`)
- **Subcommands**:
  - `dcr sync` — Sync database with **both** cascade `.pb` files and devin_local `sessions.db` (incremental, archives stale conversations — never deletes)
  - `dcr search <query>` — Full-text search with `-p/--project`, `-s/--source`, `-l/--limit` filters
  - `dcr list` — List conversations with `-l/--limit`, `-p/--project` (exact or prefix match), `--no-sync`, shows `source_type`
  - `dcr show <cascade_id>` — Show conversation details (supports UUID prefix, slug, or numeric DB id)
  - `dcr export <cascade_id>` — Export conversation as structured markdown (rounds → steps with full content, checkpoints). Supports `-o/--output` for file output, UUID prefix, slug, or numeric DB id.
  - `dcr status` — Database statistics (per-source breakdown: cascade vs devin_local)
  - `dcr html` — Generate sortable HTML overview (`-o/--output`), date columns use `data-sort` attribute with Unix timestamp for correct numeric sorting
- **Auto-sync**: Enabled by default for `search`, `list`, `html` (disable with `--no-sync`)
- **Global option**: `--db <path>` to override database location

### `server.py` — MCP Server (Rejected)

- **Status**: Rejected — see [ADR-0004](decisions/0004-cli-over-mcp.md)
- **Rationale**: MCP server imposes permanent token cost (~3-5K tokens/turn) for tools used occasionally. CLI (`dcr`) already complete with 7 subcommands and 177 tests. 0/9 decision criteria favor MCP for this use case.
- **Integration path**: DCR integrates with Cascade via CLI calls (`run_command`) and optionally via a dedicated skill. No MCP configuration needed.

## Data Flow

1. **On `dcr sync`**: Scan **both** sources:
   - **Cascade**: `~/.codeium/windsurf/cascade/*.pb` → decrypt → parse → index (incremental on mtime+size). Missing `.pb` → archive (archived=1, never delete). (Parser enrichment — thinking/tool_calls — deferred to Phase 1B; current parser extracts `content_text` only.)
   - **Devin Local**: `~/.local/share/devin/cli/sessions.db` (read-only) → read sessions + **all** `message_nodes` (full tree, `json.loads(chat_message)` per node) → compute `on_main_chain` via tip→root walk → index (incremental on `last_activity_at`). Compaction nodes → `checkpoints`. Missing sessions → archive (never delete).
2. **On `dcr search`**: Auto-sync (indexes new/modified, archives stale) → FTS5 query across rounds/steps/checkpoints → ranked results with snippets
3. **On `dcr show`**: Fetch conversation from SQLite → display metadata, rounds, steps, checkpoints
4. **On `dcr html`**: Auto-sync → generate sortable HTML table of all conversations
5. **On `dcr export`**: Fetch conversation from SQLite → output structured markdown with rounds, steps (full content text), and checkpoints to stdout or file

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `mcp` | >=1.27,<2 | MCP server SDK (FastMCP) — for M7 (deferred) |
| `cryptography` | >=43.0 | AES-256-GCM decryption |
| `protobuf` | >=5.0 | Protobuf wire-format parsing |
| `pydantic` | >=2.0 | Data models & validation |

## Performance Considerations

- Decryption: ~0.1s per file (5MB average)
- Parsing: ~0.05s per file
- Indexing: ~0.5s per file (FTS5 insert)
- Full batch (50 files): ~30s total
- Search: <10ms (FTS5 with BM25)
- Database size: ~50-100MB for 50 conversations

## Security

- The AES key is a **known global constant** (not a secret) — see ADR-0001
- All data stays local — no network calls
- `artifacts/` directory is gitignored (contains decrypted user data)
- No authentication needed (local stdio transport only)

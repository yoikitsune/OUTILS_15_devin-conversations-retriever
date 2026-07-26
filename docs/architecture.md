# Architecture — Devin Conversations Retriever

> Last updated: 2026-07-26

## Overview

```
~/.codeium/windsurf/cascade/*.pb
        │
        ▼
  ┌─────────────┐
  │  decrypt.py  │  AES-256-GCM decryption
  │  (reuse)     │  Key: safeCodeiumworldKeYsecretBalloon
  └──────┬───────┘
         │ plaintext protobuf bytes
         ▼
  ┌─────────────┐
  │  parser.py   │  Protobuf wire-format parsing
  │  (reuse)     │  CortexTrajectory → steps → rounds
  └──────┬───────┘
         │ structured conversation data
         ▼
  ┌─────────────┐
  │  indexer.py  │  SQLite + FTS5 indexing
  │  (new)       │  conversations, rounds, steps tables
  └──────┬───────┘
         │ indexed DB
         ▼
  ┌─────────────┐
  │  search.py   │  FTS5 full-text search
  │  (new)       │  with filters (project, date, type)
  └──────┬───────┘
         │ search results
         ▼
  ┌─────────────┐
  │  server.py   │  MCP server (FastMCP, stdio)
  │  (new)       │  Exposes tools to Cascade/any MCP client
  └─────────────┘
```

## Modules

### `decrypt.py` — Decryption

- **Source**: Adapted from `windsurf-local-user-data-decryption/tools/decrypt_pb.py`
- **Input**: `.pb` file path
- **Output**: Raw protobuf bytes
- **Algorithm**: AES-256-GCM, key = `safeCodeiumworldKeYsecretBalloon`
- **File format**: `[nonce 12B][ciphertext][GCM tag 16B]`

### `parser.py` — Protobuf Parsing

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
  - `steps`: List of `StepInfo` with `type`, `status`, `variant_field`, `variant_data`, `content_text`, `timestamp`, `model`
  - `checkpoints`: List of `CheckpointInfo` with summaries, edited files, plan snapshots
  - `rounds`: List of `RoundInfo` grouping steps by user input cycles
- **Key variant_fields**:
  - `19` = user_input (user's prompt)
  - `20` = planner_response (AI's response, field 8 = visible text)
  - `28` = run_command (shell commands)
  - `30` = checkpoint (compression summary)
  - `37` = command_result (command output)
- **Title derivation logic**:
  1. `conversation_title` from any checkpoint (field 10) — usually empty
  2. First line of `user_intent` from first checkpoint (field 4) — e.g. "Merge Conflict Resolution\n..."
  3. First user prompt truncated to 80 chars
  4. `cascade_id` or `trajectory_id` as last resort

### `indexer.py` — SQLite + FTS5 Indexing

- **Database**: `~/.local/share/dcr/dcr.db` (or configurable)
- **Tables**:
  - `conversations`: id, cascade_id, trajectory_id, title, trajectory_type, source, project_path, git_branch, model, created_at, updated_at, step_count, round_count, checkpoint_count, pb_mtime, pb_size, indexed_at
  - `rounds`: id, conversation_id, round_number, prompt, start_step, end_step
  - `steps`: id, conversation_id, step_index, type, status, variant_field, content_text, timestamp, model
  - `checkpoints`: id, conversation_id, step_index, checkpoint_index, user_intent, session_summary, code_change_summary, memory_summary, conversation_title, plan_snapshot, intent_only, included_step_index_start, included_step_index_end, edited_files
- **FTS5 virtual tables**: `rounds_fts` (prompt), `steps_fts` (content_text), `checkpoints_fts` (user_intent, session_summary, code_change_summary, memory_summary, conversation_title)
- **Triggers**: 9 auto-sync triggers (insert/delete/update on each FTS5 table)
- **Indexes**: cascade_id, project_path, created_at, conversation_id (rounds/steps/checkpoints)
- **Indexing strategy**: Incremental — skip files where mtime + size match existing record

### `search.py` — Search Engine

- **Query type**: FTS5 full-text (BM25 ranking)
- **Filters**: conversation_id, date range, step type, variant_field
- **Result format**: List of matches with conversation title, round number, step index, snippet, score
- **Limit**: Configurable, default 50

### `server.py` — MCP Server

- **Framework**: FastMCP (official Python SDK)
- **Transport**: stdio (local)
- **Tools**:
  - `search_conversations(query, limit?, project?, date_from?, date_to?)` — Full-text search
  - `list_conversations(limit?, project?)` — List with metadata
  - `get_conversation(cascade_id, format?)` — Full conversation in Markdown
  - `get_round(cascade_id, round_number)` — Specific round
  - `decrypt_all()` — Decrypt + index new/modified `.pb` files
  - `index_status()` — Indexing progress and stats

### `models.py` — Pydantic Models

- `Conversation`, `Round`, `Step`, `Checkpoint`, `SearchResult`
- Input validation for all MCP tool parameters

## Data Flow

1. **On `decrypt_all`**: Scan `~/.codeium/windsurf/cascade/*.pb`, decrypt each, parse, index in SQLite
2. **On `search_conversations`**: FTS5 query → ranked results with snippets
3. **On `get_conversation`**: Fetch from SQLite → render as Markdown (reuse `export_md.py` logic)
4. **On `get_round`**: Fetch specific round → render as Markdown

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `mcp` | >=1.27,<2 | MCP server SDK (FastMCP) |
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

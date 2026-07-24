# Architecture — Devin Conversations Retriever

> Last updated: 2026-07-24

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
- **Output**: Structured `CortexTrajectory` with:
  - `trajectory_id`: UUID
  - `cascade_id`: UUID (filename stem)
  - `steps`: List of step dicts with `type`, `variant_field`, `variant_data`
  - `checkpoints`: List of checkpoint summaries
- **Key variant_fields**:
  - `19` = user_input (user's prompt)
  - `20` = planner_response (AI's response + internal planning)
  - `28` = run_command (shell commands)
  - `30` = checkpoint (compression summary)
  - `37` = command_result (command output)

### `indexer.py` — SQLite + FTS5 Indexing

- **Database**: `~/.local/share/dcr/dcr.db` (or configurable via env)
- **Tables**:
  - `conversations`: id, cascade_id, trajectory_id, title, created_at, step_count, round_count
  - `rounds`: id, conversation_id, round_number, prompt, start_step, end_step
  - `steps`: id, conversation_id, round_id, step_index, type, variant_field, content_text
  - `checkpoints`: id, conversation_id, step_index, user_intent, session_summary, code_change_summary
- **FTS5 virtual tables**: on `rounds.prompt`, `steps.content_text`, `checkpoints.*`
- **Indexing strategy**: Incremental — only re-index new/modified `.pb` files (based on mtime hash)

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

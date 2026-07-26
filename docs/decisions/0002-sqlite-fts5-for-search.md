# ADR-0002: SQLite + FTS5 for Full-Text Search

> Status: Accepted
> Date: 2026-07-24

## Context

We need to index and search across all decrypted conversation content (user messages, AI responses, tool calls, checkpoints). The search must be fast, local, and support filtering by conversation, date, and step type.

## Decision

Use **SQLite with FTS5** (Full-Text Search 5) as the search engine.

## Rationale

- **Built into Python stdlib**: `sqlite3` module ships with Python — zero extra dependencies
- **FTS5 is powerful**: BM25 ranking, prefix queries, phrase queries, column weights
- **Fast**: Sub-10ms queries for typical workloads (<100MB DB)
- **Single-file database**: Easy to backup, move, or reset
- **Proven pattern**: Used by `deja`, `lore`, and `ClaudeHistoryMCP` for similar use cases
- **No server process**: SQLite is embedded — no port conflicts, no daemon to manage

## Alternatives Considered

- **Vector embeddings (semantic search)**: More complex, requires ONNX runtime + embedding model. Overkill for keyword-based search. Can be added later as a hybrid layer.
- **Whoosh/Tantivy**: More features but external dependencies. FTS5 is sufficient.
- **ripgrep over Markdown files**: Works but no ranking, no metadata filtering, slower for large corpora.

## Consequences

- Database file at `~/.local/share/dcr/dcr.db` (configurable via `DCR_DB_PATH` env var)
- Incremental indexing based on file mtime to avoid full re-index on every run
- **Permanent archive**: conversations whose `.pb` file is removed by Windsurf are marked `archived=1` but are never deleted from the database — they remain fully searchable
- No semantic search initially — keyword/FTS only (can be extended later)

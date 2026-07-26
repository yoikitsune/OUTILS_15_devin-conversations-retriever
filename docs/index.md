# docs/index.md — Source-of-Truth Router

> Last updated: 2026-07-26 (CLI UX improvements)

## Project

**Devin Conversations Retriever (DCR)** — A CLI tool that decrypts, indexes, and enables full-text search across local Windsurf Cascade conversation histories (`.pb` files). The SQLite database is a **permanent archive** — conversations are never deleted, even when the source `.pb` file is removed by Windsurf. CLI-only — MCP server rejected (see ADR-0004).

## Why

Windsurf stores conversation histories as encrypted protobuf files locally. `trajectory_search` is limited to 50 chunks per query and can't search across conversations. DCR decrypts all conversations, indexes them in a permanent SQLite FTS5 archive, and exposes search via a CLI — enabling both AI agents and humans to find any past discussion. Conversations whose `.pb` file is later removed by Windsurf are **archived, not deleted**.

## Documentation Map

| Document | Purpose | When to Read |
|---|---|---|
| [`/AGENTS.md`](../AGENTS.md) | Entry point for AI agents — stack, structure, conventions | First — always |
| [`/progress.md`](../progress.md) | Living status board — what's done, in progress, blocked | Every session start |
| [`/docs/architecture.md`](architecture.md) | Technical architecture — modules, data flow, schemas | Before touching code |
| [`/docs/decisions/`](decisions/) | Architecture Decision Records (ADRs) | When questioning a design choice |
| [`/.devin/AGENTS.md`](../.devin/AGENTS.md) | Cascade-specific instructions | When working inside Windsurf |

## Source Modules

| Module | Purpose | Status |
|---|---|---|
| [`/src/dcr/decrypt.py`](../src/dcr/decrypt.py) | AES-256-GCM decryption of `.pb` files | Completed (M2) |
| [`/src/dcr/parser.py`](../src/dcr/parser.py) | Protobuf wire-format parsing | Completed (M3) |
| [`/src/dcr/indexer.py`](../src/dcr/indexer.py) | SQLite + FTS5 indexing with sync() | Completed (M4) |
| [`/src/dcr/search.py`](../src/dcr/search.py) | FTS5 search engine with filters and auto-sync | Completed (M5) |
| [`/src/dcr/cli.py`](../src/dcr/cli.py) | CLI interface (`dcr`) with 7 subcommands | Completed (M6) |
| [`/src/dcr/server.py`](../src/dcr/server.py) | MCP server (FastMCP) | Rejected (M7) — see [ADR-0004](decisions/0004-cli-over-mcp.md) |

## Decision Records

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](decisions/0001-use-python-mcp-sdk.md) | Use Python + MCP SDK (FastMCP) | Accepted (MCP rationale superseded by ADR-0004) |
| [ADR-0002](decisions/0002-sqlite-fts5-for-search.md) | SQLite + FTS5 for full-text search | Accepted |
| [ADR-0003](decisions/0003-reuse-windsurf-decrypt-tools.md) | Reuse windsurf-local-user-data-decryption tools | Accepted |
| [ADR-0004](decisions/0004-cli-over-mcp.md) | CLI + Skill over MCP server | Accepted |

## Verification

```bash
# Run all tests (125 tests)
.venv/bin/pytest tests/ -v

# CLI usage
.venv/bin/dcr sync       # Sync DB with cascade .pb files (archives stale, never deletes)
.venv/bin/dcr status     # Show DB stats (active + archived counts)
.venv/bin/dcr list -l 5  # List 5 most recent conversations
.venv/bin/dcr list -p /path/to/project  # Filter by project path
.venv/bin/dcr search "protobuf"  # Full-text search (includes archived)
.venv/bin/dcr show 04a36d38       # Show conversation (UUID prefix or numeric DB id)
.venv/bin/dcr export 04a36d38     # Export conversation as markdown
.venv/bin/dcr html                # Generate HTML overview
```

# docs/index.md — Source-of-Truth Router

> Last updated: 2026-07-24

## Project

**Devin Conversations Retriever (DCR)** — An MCP server that decrypts, indexes, and enables full-text search across local Windsurf Cascade conversation histories (`.pb` files).

## Why

Windsurf stores conversation histories as encrypted protobuf files locally. `trajectory_search` is limited to 50 chunks per query and can't search across conversations. DCR decrypts all conversations, indexes them in SQLite FTS5, and exposes search via MCP tools — enabling both AI agents and humans to find any past discussion.

## Documentation Map

| Document | Purpose | When to Read |
|---|---|---|
| [`/AGENTS.md`](../AGENTS.md) | Entry point for AI agents — stack, structure, conventions | First — always |
| [`/progress.md`](../progress.md) | Living status board — what's done, in progress, blocked | Every session start |
| [`/docs/architecture.md`](architecture.md) | Technical architecture — modules, data flow, schemas | Before touching code |
| [`/docs/decisions/`](decisions/) | Architecture Decision Records (ADRs) | When questioning a design choice |
| [`/.devin/AGENTS.md`](../.devin/AGENTS.md) | Cascade-specific instructions | When working inside Windsurf |

## Decision Records

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](decisions/0001-use-python-mcp-sdk.md) | Use Python + MCP SDK (FastMCP) | Accepted |
| [ADR-0002](decisions/0002-sqlite-fts5-for-search.md) | SQLite + FTS5 for full-text search | Accepted |
| [ADR-0003](decisions/0003-reuse-windsurf-decrypt-tools.md) | Reuse windsurf-local-user-data-decryption tools | Accepted |

## Verification

```bash
# Run tests
.venv/bin/pytest tests/ -v

# Check MCP server starts
.venv/bin/devin-conversations-retriever --help

# Decrypt + index
.venv/bin/dcr decrypt-all
.venv/bin/dcr index
```

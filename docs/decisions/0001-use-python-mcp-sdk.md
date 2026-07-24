# ADR-0001: Use Python + MCP SDK (FastMCP)

> Status: Accepted
> Date: 2026-07-24

## Context

We need to build an MCP server that decrypts Windsurf `.pb` files, parses protobuf, indexes in SQLite FTS5, and exposes search tools. The existing decryption tools (`decrypt_pb.py`, `scan_trajectory.py`, `export_md.py`) are already in Python. Multiple MCP servers for conversation search exist (lore, deja, RepoChatMCP) — all use either Python or Node.js.

## Decision

Use **Python 3.10+** with the **official MCP Python SDK** (`mcp` package, FastMCP high-level API).

## Rationale

- **Reuse existing tools**: `decrypt_pb.py` and `scan_trajectory.py` are already Python — no porting needed
- **MCP SDK maturity**: Official Python SDK with FastMCP decorators, Pydantic validation, stdio transport
- **SQLite FTS5**: Built into Python's `sqlite3` stdlib — no extra dependencies for search
- **Ecosystem**: `cryptography` and `protobuf` are first-class Python packages
- **Cascade compatibility**: MCP stdio transport is fully supported by Windsurf Cascade

## Alternatives Considered

- **Node.js/TypeScript**: Would require porting decryption + parsing logic. No advantage since existing tools are Python.
- **Rust**: Overkill for this project. Better performance but much more development effort.

## Consequences

- Python 3.10+ required on the host machine
- venv needed for dependency isolation
- stdio transport only (no HTTP server needed for local tool)

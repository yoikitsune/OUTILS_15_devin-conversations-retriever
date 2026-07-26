# AGENTS.md — Devin Conversations Retriever

> MCP server to decrypt, index, and search local Windsurf Cascade conversation histories.

## Quick Start

```bash
# Setup
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Run MCP server (stdio)
.venv/bin/devin-conversations-retriever

# Decrypt + index all conversations
# (via MCP tool or CLI)
.venv/bin/dcr decrypt-all
.venv/bin/dcr index
```

## Tech Stack

- **Language**: Python 3.10+
- **MCP SDK**: `mcp` (official Python SDK, FastMCP)
- **Encryption**: `cryptography` (AES-256-GCM decryption)
- **Protobuf**: `protobuf` (parsing CortexTrajectory)
- **Search**: SQLite + FTS5 (full-text search)
- **Transport**: stdio (local MCP)

## Project Structure

```
.
├── AGENTS.md              # You are here — entry point for AI agents
├── .devin/                # Cascade configuration
│   ├── AGENTS.md          # Cascade-specific instructions
│   └── rules/             # Behavioral rules
├── docs/
│   ├── index.md           # Source-of-truth router
│   ├── architecture.md    # Technical architecture
│   └── decisions/         # Architecture Decision Records (ADR)
├── progress.md            # Living progress tracker
├── pyproject.toml         # Project config
├── src/
│   └── dcr/               # Main package
│       ├── __init__.py
│       ├── server.py      # MCP server entry point
│       ├── decrypt.py     # .pb decryption module
│       ├── parser.py      # Protobuf parsing (CortexTrajectory)
│       ├── indexer.py     # SQLite + FTS5 indexing
│       ├── search.py      # Search engine
│       ├── cli.py        # CLI interface (dcr)
│       └── models.py      # Pydantic models
├── tests/
│   ├── test_decrypt.py
│   ├── test_parser.py
│   ├── test_indexer.py
│   ├── test_search.py
│   └── test_cli.py
└── artifacts/             # Decrypted/exported files (gitignored)
```

## Conventions

- Python code follows PEP 8, type hints required on all public functions
- Docstrings on all public functions (Google style)
- Tests in `tests/`, mirror `src/` structure
- No hardcoded secrets — the AES key is a known constant (see `docs/decisions/`)
- Keep `AGENTS.md`, `progress.md`, and `docs/index.md` up to date after each session

## What NOT to Do

- Don't create files in `.windsurf/` — use `.devin/` instead
- Don't commit `artifacts/` — it contains decrypted user data
- Don't add generic coding rules — they're already in Cascade's training data
- Don't skip tests — every module must have corresponding test files

## Current State

See `progress.md` for the live status board and `docs/index.md` for the full documentation router.

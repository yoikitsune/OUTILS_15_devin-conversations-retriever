# Devin Conversations Retriever (DCR)

Decrypt, index, and permanently archive your local Windsurf Cascade conversation histories.

## Why?

Windsurf stores conversation histories as AES-256-GCM encrypted protobuf files in `~/.codeium/windsurf/cascade/`. The built-in `trajectory_search` is limited to 50 chunks per query and can't search across conversations. DCR solves this by:

- **Decrypting** all `.pb` files using the known AES key
- **Parsing** the protobuf wire format without compiled schemas
- **Indexing** conversations in a permanent SQLite archive with FTS5 full-text search
- **Archiving** conversations whose `.pb` file is later removed — they are never deleted from the database
- **Searching** across all conversations (active and archived) with BM25 ranking and filters

## Quick Start

```bash
# Install
git clone <repo-url> && cd devin-conversations-retriever
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Sync database with your Cascade conversations
.venv/bin/dcr sync

# Search
.venv/bin/dcr search "protobuf parsing"

# List conversations
.venv/bin/dcr list -l 10

# Show a specific conversation (prefix matching works)
.venv/bin/dcr show 04a36d38

# Generate HTML overview
.venv/bin/dcr html

# Check database status
.venv/bin/dcr status
```

## CLI Reference

```
dcr [--db DB_PATH] <command> [options]

Commands:
  sync       Sync database with cascade .pb files (archives stale, never deletes)
  search     Full-text search conversations
  list       List indexed conversations
  show       Show a specific conversation (supports ID prefix)
  status     Show database statistics
  html       Generate sortable HTML overview

Search options:
  -l, --limit N        Max results (default: 20)
  -p, --project PATH   Filter by project path
  -s, --source TABLE   Restrict to rounds|steps|checkpoints
  --no-sync            Skip auto-sync before search

Global:
  --db PATH            Override database location (default: ~/.local/share/dcr/dcr.db)
```

## What Gets Extracted

Each conversation is indexed with:

| Field | Source | Example |
|---|---|---|
| `title` | First line of checkpoint `user_intent` | "Merge Conflict Resolution" |
| `project_path` | Protobuf field 7 → 1 → 1 | `/home/user/projects/myapp` |
| `git_branch` | Protobuf field 7 → 1 → 4 | `main`, `features/auth` |
| `model` | Step metadata field 28 | `glm-5-2` |
| `created_at` | First step timestamp | `1721900000.0` |
| `updated_at` | Last step timestamp | `1721980000.0` |
| `steps` | Each step with content, timestamp, model | — |
| `rounds` | Grouped by user input cycles | — |
| `checkpoints` | Summaries, edited files, plan snapshots | — |

## Architecture

```
.pb files → decrypt.py → parser.py → indexer.py → search.py → cli.py
              AES-256     protobuf     SQLite+FTS5    BM25       argparse
              GCM         wire-format  permanent      filters
                                         archive
```

> **The SQLite database is a permanent archive.** Once a conversation is indexed,
> it is never deleted — even if the source `.pb` file is removed by Windsurf.

| Module | Purpose | Tests |
|---|---|---|
| `decrypt.py` | AES-256-GCM decryption | 10 |
| `parser.py` | Protobuf wire-format parsing | 23 |
| `indexer.py` | SQLite + FTS5 indexing + sync + archival | 34 |
| `search.py` | FTS5 search with filters + auto-sync | 24 |
| `cli.py` | CLI with 7 subcommands | 25 |
| **Total** | | **116** |

## Database Schema

**Tables**: `conversations`, `rounds`, `steps`, `checkpoints`
**FTS5**: `rounds_fts` (prompt), `steps_fts` (content_text), `checkpoints_fts` (user_intent, session_summary, ...)
**Triggers**: 9 auto-sync triggers (insert/delete/update per FTS5 table)
**Location**: `~/.local/share/dcr/dcr.db`

## Development

```bash
# Run tests
.venv/bin/pytest tests/ -v

# Run specific module tests
.venv/bin/pytest tests/test_search.py -v
```

## Tech Stack

- **Language**: Python 3.10+
- **Encryption**: `cryptography` (AES-256-GCM)
- **Parsing**: `protobuf` (wire-format, no schema compilation)
- **Search**: SQLite + FTS5 (BM25 ranking)
- **CLI**: `argparse`
- **Testing**: `pytest` (116 tests)

## Sources

- Decryption and parsing logic adapted from [windsurf-local-user-data-decryption](https://github.com/dayearleo/windsurf-local-user-data-decryption) (MIT)
- The AES key (`safeCodeiumworldKeYsecretBalloon`) is a known global constant — see [ADR-0001](docs/decisions/0001-use-python-mcp-sdk.md)

## Project Structure

```
.
├── src/dcr/
│   ├── decrypt.py    # AES-256-GCM decryption
│   ├── parser.py     # Protobuf wire-format parser
│   ├── indexer.py    # SQLite + FTS5 indexer with sync()
│   ├── search.py     # FTS5 search engine
│   └── cli.py        # CLI interface (dcr)
├── tests/            # 116 tests
├── docs/             # Architecture, ADRs, index
├── progress.md       # Living status board
└── pyproject.toml    # Dependencies + entry points
```

## License

MIT

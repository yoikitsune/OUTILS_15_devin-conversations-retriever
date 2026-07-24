# .devin/AGENTS.md — Devin Conversations Retriever

## Project Identity

- **Name**: Devin Conversations Retriever (DCR)
- **Type**: MCP server (Python, stdio transport)
- **Purpose**: Decrypt, index, and search Windsurf Cascade conversation histories

## Inventory

### Rules
(none yet)

### Skills
- `cascade-self-config` (global skill, project references in `.devin/skills/cascade-self-config/references/`)

### Workflows
(none yet)

## Development Commands

```bash
# Setup
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Test
.venv/bin/pytest tests/ -v

# Run MCP server
.venv/bin/devin-conversations-retriever

# CLI
.venv/bin/dcr decrypt-all
.venv/bin/dcr index
.venv/bin/dcr search "query"
```

## Key Files

- `progress.md` — current status, read first
- `docs/architecture.md` — technical design before coding
- `docs/decisions/` — ADRs for design rationale
- `artifacts/` — gitignored, contains decrypted data

## Conventions

- All new code in `src/dcr/`
- Tests mirror `src/` structure in `tests/`
- Update `progress.md` at end of each session
- The AES key is a known constant, not a secret

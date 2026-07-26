# .devin/AGENTS.md — Devin Conversations Retriever

## Project Identity

- **Name**: Devin Conversations Retriever (DCR)
- **Type**: MCP server (Python, stdio transport)
- **Purpose**: Decrypt, index, and search Windsurf Cascade conversation histories

## Inventory

### Rules
- `update-docs` (model_decision) — met a jour progress.md, docs/architecture.md, docs/index.md, AGENTS.md quand un milestone est complete ou en fin de session
- `definition-of-done` (model_decision) — criteres pour marquer un milestone comme termine
- `test-with-code` (model_decision) — exige un test par module avant de passer au milestone suivant
- `git-commit-discipline` (model_decision) — un commit par feature/milestone, tests avant commit, pas de commit en bloc

### Skills
- `cascade-self-config` (global skill, project references in `.devin/skills/cascade-self-config/references/`)

### Workflows
- `/end-session` — protocole de handoff en fin de session

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
- `docs/index.md` — documentation router
- `docs/decisions/` — ADRs for design rationale
- `src/dcr/decrypt.py` — AES-256-GCM decryption module
- `src/dcr/parser.py` — protobuf wire-format parser
- `src/dcr/indexer.py` — SQLite + FTS5 indexer with sync()
- `artifacts/` — gitignored, contains decrypted data

## Conventions

- All new code in `src/dcr/`
- Tests mirror `src/` structure in `tests/`
- Update `progress.md` at end of each session
- The AES key is a known constant, not a secret

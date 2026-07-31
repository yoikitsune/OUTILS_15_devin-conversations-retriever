# .devin/AGENTS.md — Devin Conversations Retriever

## Project Identity

- **Name**: Devin Conversations Retriever (DCR)
- **Type**: MCP server (Python, stdio transport)
- **Purpose**: Decrypt, index, and permanently archive Windsurf Cascade conversation histories. The SQLite database is a permanent archive — conversations are never deleted.

## Inventory

### Rules
- `update-docs` (model_decision) — met a jour progress.md, docs/architecture.md, docs/index.md, AGENTS.md quand un milestone est complete ou en fin de session
- `definition-of-done` (model_decision) — criteres pour marquer un milestone comme termine
- `test-with-code` (model_decision) — exige un test par module avant de passer au milestone suivant ; suite complete sur modification d'un module existant
- `git-commit-discipline` (model_decision) — granularite au cas par cas, validation utilisateur avant commit, tests avant commit, pas de commit en bloc
- `task-sequencing` (model_decision) — execute les taches d'une phase sequentiellement, valide tests + utilisateur avant de passer a la suivante

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
.venv/bin/dcr sync
.venv/bin/dcr search "query"
.venv/bin/dcr list [-p <project>]
.venv/bin/dcr show <id_or_uuid>
.venv/bin/dcr export <id_or_uuid> [-o file]
.venv/bin/dcr status
.venv/bin/dcr html
```

## Key Files

- `progress.md` — current status, read first
- `docs/architecture.md` — technical design before coding
- `docs/index.md` — documentation router
- `docs/decisions/` — ADRs for design rationale
- `src/dcr/decrypt.py` — AES-256-GCM decryption module
- `src/dcr/parser.py` — protobuf wire-format parser
- `src/dcr/indexer.py` — SQLite + FTS5 indexer with sync() and archival (stale conversations are archived, never deleted)
- `src/dcr/search.py` — FTS5 search engine with filters and auto-sync
- `src/dcr/cli.py` — CLI interface with 7 subcommands
- `artifacts/` — gitignored, contains decrypted data

## Conventions

- All new code in `src/dcr/`
- Tests mirror `src/` structure in `tests/`
- Update `progress.md` at end of each session
- The AES key is a known constant, not a secret

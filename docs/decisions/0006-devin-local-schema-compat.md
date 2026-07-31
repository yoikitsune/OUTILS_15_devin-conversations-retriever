# ADR-0006: Devin Local Schema Compatibility Strategy

> Status: Accepted
> Date: 2026-07-31

## Context

Devin Local stores conversation data in `~/.local/share/devin/cli/sessions.db`, a SQLite
database managed by the `refinery` migration framework. As of 2026-07-31, the schema is at
**version 16** (16 additive migrations). `dcr` reads this database in `mode=ro` and parses
its content into `TrajectoryInfo` objects.

The risk: **Devin Desktop ships new migrations** (e.g. new columns, new tables, renamed
fields). If `dcr` is not updated, it may:
- Miss new data (silent — sync works but doesn't capture new fields)
- Break on renamed/removed columns (loud — sync fails with `sqlite3.OperationalError`)

The refinery framework is **additive by design** — migrations only add columns/tables, never
remove or rename (with one historical exception: migration 13 renamed `permission_mode` to
`agent_mode`). This means new versions are generally backward-compatible: `dcr` will keep
working, it just won't see the new fields.

## Decision

**Track schema version explicitly, warn on drift, fail loudly on incompatibility.**

### 1. `KNOWN_SCHEMA_VERSION` constant

`src/dcr/devin_local.py` exports `KNOWN_SCHEMA_VERSION = 16`. This is the version `dcr` was
built and tested against. It's updated manually after verifying compatibility with a new
Devin Desktop release.

### 2. `check_schema()` in `devin_local.py` (already exists — Phase 1A)

`DevinLocalReader.check_schema()` reads `refinery_schema_history.MAX(version)` and logs a
warning if the detected version is higher than `KNOWN_SCHEMA_VERSION`. This runs on every
`read_session()` call — the warning appears in logs but doesn't block sync.

### 3. `scripts/check_devin_schema.py` (Phase 3.2)

A standalone script that performs a **deep compatibility check**:
- Schema version (detected vs known)
- Required tables exist (`sessions`, `message_nodes`, `refinery_schema_history`)
- Required columns exist in each table (all columns `devin_local.py` reads)
- `chat_message` JSON has required keys (`role`, `content`) — sampled from one row

Exit codes: `0` = ok/not_found, `1` = ahead (warning), `2` = incompatible (missing
tables/columns). Designed for CI: add as a pre-deploy or nightly check.

Usage:
```bash
python scripts/check_devin_schema.py           # human-readable
python scripts/check_devin_schema.py --json    # JSON output for CI
python scripts/check_devin_schema.py --db PATH # override DB path
```

### 4. `dcr status` displays schema version (Phase 3.1)

`dcr status` now shows:
```
Devin schema: detected v16, known v16 ✓
```
Or, if ahead:
```
Devin schema: detected v18, known v16 ⚠
  ⚠ sessions.db schema is newer than dcr supports — sync may miss new fields
```

### 5. `tests/test_schema_compat.py` (Phase 3.3)

17 tests covering:
- `check_schema()` function: ok, not_found, ahead, missing table, missing column, bad JSON,
  empty table, format_report
- Exit code mapping (0/1/2)
- `KNOWN_SCHEMA_VERSION` sanity checks
- `REQUIRED_TABLES` covers all tables `devin_local.py` reads
- **Real data tests** (skipped if no `sessions.db`): `test_real_check_schema` verifies the
  real DB is compatible; `test_real_schema_version_matches_known` **fails** if the real
  schema version is ahead of `KNOWN_SCHEMA_VERSION` — this is the CI tripwire.

### 6. CI integration (recommended, not yet implemented)

Add to CI pipeline:
```bash
# Nightly or pre-deploy check
python scripts/check_devin_schema.py --json
.venv/bin/pytest tests/test_schema_compat.py -v
```

If `test_real_schema_version_matches_known` fails, a developer must:
1. Run `python scripts/check_devin_schema.py` to see what changed
2. Check if `devin_local.py` still works (run `dcr sync` manually)
3. If compatible: update `KNOWN_SCHEMA_VERSION` in `devin_local.py`, add any new columns to
   `REQUIRED_TABLES` in `check_devin_schema.py`, commit
4. If incompatible (renamed/removed columns): update `devin_local.py` to handle the change,
   update tests, bump `KNOWN_SCHEMA_VERSION`

## Compatibility Strategy

### Additive migrations (the common case)

Refinery migrations are additive — they add columns/tables, never remove. `dcr` uses
`SELECT` with explicit column lists (not `SELECT *`), so new columns are silently ignored.
New tables are also ignored (dcr only reads `sessions`, `message_nodes`,
`refinery_schema_history`). **No code change needed** — just bump `KNOWN_SCHEMA_VERSION`
after verifying.

### Breaking migrations (the rare case)

If a migration renames or removes a column that `dcr` reads (e.g. migration 13 renamed
`permission_mode` → `agent_mode`), `dcr` will fail with `sqlite3.OperationalError` on the
first `sync`. The `check_devin_schema.py` script will catch this **before** sync fails —
it reports the missing column and exits with code 2.

### `tool_call_state` table (intentionally not tracked)

`dcr` does NOT read `tool_call_state` (Phase 2 decision — option 1, `chat_message.tool_calls`
+ tool-role nodes are the complete source). This table is therefore not in
`REQUIRED_TABLES`. If a future migration removes it, `dcr` is unaffected.

## Consequences

| Aspect | Impact |
|---|---|
| **Positive**: Early detection | `test_real_schema_version_matches_known` fails in CI before users hit the issue |
| **Positive**: Graceful degradation | Additive migrations work without code change — just bump the constant |
| **Positive**: Clear diagnostics | `dcr status` + `check_devin_schema.py` tell users exactly what's wrong |
| **Negative**: Manual constant update | `KNOWN_SCHEMA_VERSION` must be updated by hand after each Devin Desktop release |
| **Negative**: No auto-detection of new fields | If a migration adds a useful new column, `dcr` won't capture it until someone updates `devin_local.py` |
| **Neutral**: `mode=ro` | `dcr` never writes to `sessions.db`, so schema changes can't corrupt it |

## Alternatives Considered

### A1: `SELECT *` and dynamic column mapping

Use `PRAGMA table_info` at runtime to discover columns and map them dynamically. **Rejected**
— adds complexity, hides the schema contract, and makes it harder to test. Explicit column
lists are clearer and fail fast on breaking changes.

### A2: Pin to exact schema version

Fail if detected != known (not just > known). **Rejected** — too strict. Additive migrations
are safe; failing on them would block users after every Devin Desktop update. We only fail
on `>` when combined with missing columns (the `check_schema` script handles this).

### A3: Subscribe to Devin Desktop changelog

Parse the Devin Desktop release notes to detect schema changes automatically. **Rejected** —
no reliable changelog source, and the CI test (`test_real_schema_version_matches_known`) is
a simpler and more reliable tripwire.

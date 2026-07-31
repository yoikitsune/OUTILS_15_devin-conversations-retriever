# ADR-0005: Unified Schema for Devin Local + Cascade

> Status: Accepted (revised 2026-07-31 after verifying against real `sessions.db`)
> Date: 2026-07-31

## Context

Since 2026-07-30, the user switched from Cascade to **Devin Local** — the new local agent in
Devin Desktop, built in Rust, sharing the same harness as Devin CLI. Cascade is in maintenance
mode ("available through July") and will not evolve further. Devin Local is the future.

Devin Local stores conversations in a **completely different format**:

| Aspect | Cascade | Devin Local |
|---|---|---|
| Format | Encrypted `.pb` (AES-256-GCM + protobuf) | Plaintext SQLite (`sessions.db`) |
| Location | `~/.codeium/windsurf/cascade/*.pb` | `~/.local/share/devin/cli/sessions.db` |
| ID | UUID (`586311a4-…`) | Slug (`gleaming-court`) |
| Schema versioning | None (protobuf fields) | `refinery_schema_history` (16 migrations, additive) |
| Thinking | Present in `.pb` (field 3) but **discarded** by current parser | `message_nodes.chat_message.thinking.thinking` (nested JSON object) |
| Tool calls | Present in `.pb` (field 7) but **discarded** by current parser | `message_nodes.chat_message.tool_calls` (JSON array, key inside `chat_message` JSON) |
| Tool results | Partial (string extraction only) | `tool_call_state.tool_call_update_json` (full JSON, 533 rows) |
| Costs | Not available | `sessions.metadata` JSON: `total_credit_cost`, `total_acu_cost` (NOT token_input/output/cached — those don't exist) |
| Per-message tokens | Not available | `message_nodes.chat_message.metadata.num_tokens` / `.metrics` / `.telemetry` (per-node, not per-session) |
| Config/permissions | Not available | `sessions.cogs_json` (16 layers: User, Hook) |

> **Verified 2026-07-31** against the real `sessions.db` (102 sessions, 6056 message_nodes).
> `message_nodes` has NO SQL columns named `role`/`content`/`thinking`/`tool_calls` — those are
> **keys inside the `chat_message` JSON column**. The ADR's earlier draft assumed they were SQL
> columns; this was wrong and has been corrected throughout.

The current `dcr` parser (`extract_step_text`) performs naive string extraction from protobuf —
it recovers visible text for full-text search but **throws away** structured data (thinking,
tool calls with arguments, command results). This was acceptable for search-only use but
limits the value of the archive.

### Discovery during analysis

Inspecting a real `.pb` file revealed that Cascade's protobuf **already contains** rich
structured data that the parser discards:

- **Planner response (variant 20)**: field 1 = visible text, field 3 = thinking, field 7 =
  tool call (sub-fields: id, name, arguments JSON), field 8 = visible text duplicate
- **Run command (variant 28)**: field 23 = command string, field 24 = output, field 28 = shell

This means enriching the Cascade parser is **retroactive** — a re-index of existing `.pb`
files would recover thinking and tool calls from all past Cascade conversations.

### Devin Local schema stability

Devin Local uses `refinery` for schema migrations — 16 additive migrations since 2026-04-27.
The schema is read-only from `dcr`'s perspective (opened in `mode=ro`). New migrations are
additive (new columns/tables), so `dcr` must be resilient to unknown columns.

## Decision

**Use a unified schema with `source_type` discriminator and enriched columns.** Both Cascade
and Devin Local conversations are stored in the same tables (`conversations`, `rounds`,
`steps`, `checkpoints`), distinguished by a `source_type` column (`'cascade'` or
`'devin_local'`).

### D1: Unified schema + enriched columns

Add the following columns to the existing schema (via idempotent `ALTER TABLE` migrations,
following the existing `MIGRATION_SQL` pattern):

**`conversations`**:
- `source_type TEXT DEFAULT 'cascade'` — discriminator
- `agent_mode TEXT` — Devin Local mode. **Verified values**: `normal`, `accept-edits`, `bypass`, `''` (empty, 6 legacy sessions). NOT an enum — stored as free TEXT to absorb future Devin Desktop modes without migration.
- `credit_cost REAL` — from `sessions.metadata.total_credit_cost` (JSON)
- `acu_cost REAL` — from `sessions.metadata.total_acu_cost` (JSON)
- `token_input INTEGER`, `token_output INTEGER`, `token_cached INTEGER` — **REMOVED**. These fields do not exist in `sessions.metadata`. Per-message token counts live in `message_nodes.chat_message.metadata.num_tokens` and are not aggregated at session level. If session-level token aggregation is later needed, it must be computed by `devin_local.py` at read time (sum over nodes).

**`steps`**:
- `role TEXT` — message role (user/assistant/system/tool) — native to Devin Local (key in `chat_message` JSON), derived for Cascade
- `thinking TEXT` — reasoning text (field 3 for Cascade; `chat_message.thinking.thinking` for Devin Local — note the nested object)
- `tool_calls_json TEXT` — JSON array of tool calls (field 7 for Cascade; `chat_message.tool_calls` for Devin Local)
- `tool_call_id TEXT` — tool call ID (key `chat_message.tool_call_id` for Devin Local tool-role nodes)
- `node_id INTEGER` — Devin Local `message_nodes.node_id` (NULL for Cascade). Stable per session.
- `parent_node_id INTEGER` — Devin Local `message_nodes.parent_node_id` (NULL for Cascade and for tree roots). Preserves the forest structure for branch reconstruction.
- `on_main_chain INTEGER` — 1 if the node is on `sessions.main_chain_id`'s chain (tip → root walk), 0 otherwise. Lets `dcr show` render the linear conversation the user saw, while `dcr show --full-tree` (Phase 2) can surface lateral branches (regenerations, edited prompts).

Cascade-specific columns (`trajectory_type`, `variant_field`, `pb_mtime`, `pb_size`) remain
and are NULL for Devin Local. Devin Local-specific columns (`agent_mode`, `credit_cost`,
`acu_cost`, `node_id`, `parent_node_id`, `on_main_chain`) remain and are NULL for Cascade.

**Rationale**: `search.py`, `cli.py` (show/export/list/html) require **no logic changes** —
they query the same tables. The `source_type` column enables optional filtering
(`--source cascade|devin_local`) as a future enhancement (Phase 2).

### D2: `sync()` auto-detects both sources

`sync()` is extended to scan both sources automatically:

```python
def sync(self, cascade_dir=None, devin_local_db=None) -> dict:
    cascade_result = self._sync_cascade(cascade_dir)
    devin_result = self._sync_devin_local(devin_local_db)
    return {**cascade_result, "devin_local": devin_result}
```

- **Cascade**: unchanged — scan `*.pb`, decrypt, parse, index (incremental on mtime+size)
- **Devin Local**: open `sessions.db` in `mode=ro`, read `sessions` table, index (incremental
  on `last_activity_at`). Sessions absent from `sessions.db` are archived (same principle as
  Cascade — never delete).
- **Missing source**: if `~/.codeium/windsurf/cascade/` doesn't exist (Cascade disabled), skip
  silently. Same for `sessions.db`.

**Rationale**: the user changes nothing in their habits. `dcr sync` works as before, now
covering both sources.

### D3: Full-tree indexing + main-chain flag + compaction checkpoints

Devin Local stores messages as a **forest** (`parent_node_id`), with compaction creating new
root nodes (`metadata.extensions["compact/prior_node_ids"]`). Verified on real data: a session
with 466 nodes has only 178 on the main chain — the other 288 (62 %) are lateral branches
(regenerations, edited prompts) or pre-compaction nodes. The user's primary use case
(diagnosing Devin Local's behaviour to improve `.devin/` artifacts via `cascade-self-config`)
requires seeing **abandoned** responses, not just the final one — so lateral branches are
valuable signal, not noise.

The reconstruction strategy:

1. **Index the full tree**: every `message_nodes` row for a session becomes a `steps` row.
   Ordering: `created_at ASC, node_id ASC` (verified: `node_id` is NOT monotone with
   `created_at` — 3705 inversions on a 466-node session — so `created_at` must lead).
2. **Main-chain flag**: walk from `sessions.main_chain_id` (tip) back to root via
   `parent_node_id`, mark those nodes `on_main_chain=1`. This lets `dcr show` render the
   linear conversation the user saw, while `dcr show --full-tree` (Phase 2) surfaces
   lateral branches.
3. **Compaction checkpoints**: when a node's `metadata.extensions` contains
   `compact/prior_node_ids`, insert a row into `checkpoints` with:
   - `session_summary` = the compaction node's `content` (Devin's summary of the compacted span)
   - `included_step_index_start` / `included_step_index_end` = min/max `node_id` from
     `compact/prior_node_ids`
   - `step_index` = the compaction node's own `node_id`
   The compacted nodes remain in `steps` (full-tree principle — no data loss); the checkpoint
   just records that a compaction happened and which span it covered.
4. **Fallback**: if `main_chain_id` is NULL, set `on_main_chain=0` for all nodes and rely on
   `created_at` ordering. No crash.

**Rationale**: indexing the full tree preserves regenerations and edited prompts — exactly the
signal needed to diagnose Devin Local's behaviour. The `on_main_chain` flag keeps the default
view (`dcr show`) faithful to what the user saw, while making the full tree available on
demand. Compaction checkpoints reuse the existing `checkpoints` table without a schema change
beyond the D1 columns.

### D4: Devin Local schema version tracking

`dcr` reads `refinery_schema_history` at the start of each Devin Local sync:

- **Known version** (currently 16): proceed normally
- **Higher version** (Devin Local updated): log a warning, attempt sync anyway (schema is
  additive — new columns are ignored, existing ones still work)
- **Phase 3**: `scripts/check_devin_schema.py` + CI test to verify compatibility after each
  Devin Desktop update

**Rationale**: Devin Local evolves. The `refinery` migration system is additive by design.
`dcr` must not crash on schema evolution — degrade gracefully, warn loudly.

### D5: Enrich Cascade parser (retroactive) — deferred to Phase 1B

Extend `extract_step_text` and `parse_step` to extract structured fields currently discarded:

- **Variant 20 (planner_response)**: field 3 → `thinking`, field 7 → `tool_calls_json`
- **Variant 28 (run_command)**: field 23 → `content_text` (command), field 24 → tool result
- **Variant 37 (command_result)**: field 24 → `content_text` (output)

A re-index of existing `.pb` files recovers this data retroactively. This requires a new
`dcr sync --force` flag (does not exist in the current CLI — must be added as part of Phase 1B)
that bypasses the mtime+size incremental skip.

**Rationale**: the data is already in the `.pb` files — we were just throwing it away. However,
the user's primary use case is **Devin Local** (Cascade is in maintenance mode), and Devin
Local's `thinking`/`tool_calls` are captured for free in Phase 1A (they're keys in the
`chat_message` JSON, no extra parsing cost). Enriching the Cascade parser is therefore
**orthogonal and lower priority** — it's split into Phase 1B so Phase 1A stays small and
doesn't risk regressing the 124 existing tests. Phase 1B can be done later or skipped entirely
if Cascade enrichment turns out not to be needed.

## Devin Local → dcr mapping

> **Critical**: `message_nodes` has SQL columns `row_id, session_id, node_id, parent_node_id,
> chat_message (TEXT JSON), created_at, metadata (TEXT JSON)`. The fields `role`, `content`,
> `thinking`, `tool_calls`, `tool_call_id` are **keys inside the `chat_message` JSON string**,
> NOT SQL columns. `devin_local.py` must `json.loads(chat_message)` per node.

```
sessions.id (slug)                    → cascade_id (universal ID column)
sessions.title                        → TrajectoryInfo.title
sessions.model                        → TrajectoryInfo.model
sessions.working_directory            → TrajectoryInfo.project_path
sessions.agent_mode                   → agent_mode (new column; verified values: normal, accept-edits, bypass, '')
sessions.created_at (epoch s)         → created_at
sessions.last_activity_at             → updated_at
sessions.metadata.total_credit_cost   → credit_cost (new column)
sessions.metadata.total_acu_cost      → acu_cost (new column)
  (NO token_input/output/cached at session level — removed from schema)

message_nodes (ALL nodes, full tree)  → steps
  node_id                             → node_id (new column)
  parent_node_id                      → parent_node_id (new column)
  on main_chain (tip→root walk)       → on_main_chain (new column, 0/1)
  chat_message.role:
    user                              → variant_field=19, role='user'
    assistant                         → variant_field=20, role='assistant'
    system                            → variant_field=0,  role='system'
    tool                              → variant_field=37, role='tool'
  chat_message.content                → content_text
  chat_message.thinking.thinking      → thinking (new column; nested object — .thinking key)
  chat_message.tool_calls (JSON arr)  → tool_calls_json (new column)
  chat_message.tool_call_id           → tool_call_id (new column; tool-role nodes only)
  created_at                          → timestamp

metadata.extensions["compact/prior_node_ids"]
  → checkpoints row:
      session_summary = compaction node's chat_message.content
      included_step_index_start/end = min/max of prior_node_ids
      step_index = compaction node's node_id
```

**Ordering rule**: `steps` for a Devin Local session are ordered by `created_at ASC, node_id
ASC` (verified: `node_id` alone is NOT chronological — 3705 inversions on a 466-node session).

## Phases

### Phase 1A: Devin Local MVP — sync + full-tree indexing (priority)

Small, self-contained. Does NOT touch the Cascade parser — zero risk to the 124 existing
tests. `thinking`/`tool_calls` are captured for free (they're keys in the `chat_message` JSON).

| Task | Module | Detail |
|---|---|---|
| 1A.1 | `devin_local.py` (new) | SQLite reader: `read_sessions()` → `TrajectoryInfo` list. `json.loads(chat_message)` per node. Full-tree (all nodes), with `on_main_chain` computed via tip→root walk. Compaction nodes → `checkpoints`. |
| 1A.2 | `indexer.py` | Schema migration: `source_type`, `agent_mode`, `credit_cost`, `acu_cost` (conversations) + `role`, `thinking`, `tool_calls_json`, `tool_call_id`, `node_id`, `parent_node_id`, `on_main_chain` (steps). Idempotent `ALTER TABLE`. |
| 1A.3 | `indexer.py` | `sync()` → auto-dispatch to `_sync_cascade()` + `_sync_devin_local()`. |
| 1A.4 | `indexer.py` | `_sync_devin_local()`: incremental on `last_activity_at`, archive deleted sessions. Open `sessions.db` in `mode=ro`. |
| 1A.5 | `cli.py` | `dcr status` shows both sources. `dcr list` shows `source_type`. |
| 1A.6 | `tests/` | `test_devin_local.py`, `test_indexer_devin_local.py` (full-tree, compaction, main-chain flag, incremental, archive). |
| 1A.7 | `docs/` | This ADR + architecture.md + progress.md + index.md updates. |

### Phase 1B: Cascade parser enrichment (deferred, optional)

Orthogonal to Devin Local. Only needed if the user wants to diagnose old Cascade conversations
with the same richness as Devin Local. Can be skipped entirely if Cascade enrichment turns out
not to be worth it.

| Task | Module | Detail |
|---|---|---|
| 1B.1 | `parser.py` | Enrich Cascade extraction: thinking (field 3), tool_calls (field 7), command (field 23), result (field 24). |
| 1B.2 | `cli.py` | Add `dcr sync --force` flag (does not exist yet) to bypass mtime+size incremental skip and re-index all `.pb` files. |
| 1B.3 | `tests/` | Parser enrichment tests + `--force` flag tests. |

### Phase 2: Enrichment — exploit structured data

| Task | Detail |
|---|---|
| 2.1 | Dedicated `tool_calls` table: `id, conversation_id, step_id, tool_name, arguments_json, result_json, status`. FTS5 on arguments + result. Source: `chat_message.tool_calls` (Devin Local) + `tool_call_state` (533 rows, join on `tool_call_id`). |
| 2.2 | `dcr export` renders thinking in collapsible `<details>` blocks. |
| 2.3 | `dcr search --source cascade|devin_local` filter. |
| 2.4 | `dcr show` displays tool calls and thinking. |
| 2.5 | `dcr show --full-tree`: render lateral branches (regenerations, edited prompts) using `parent_node_id` + `on_main_chain=0`. Default `dcr show` stays main-chain only. |

### Phase 3: Resilience — track Devin Local evolution

| Task | Detail |
|---|---|
| 3.1 | `dcr status` displays detected vs supported Devin Local schema version. |
| 3.2 | `scripts/check_devin_schema.py`: compare current `sessions.db` schema with `dcr`'s known version. |
| 3.3 | CI test: `test_schema_compat.py` — verify `dcr` reads current schema without crash. |
| 3.4 | ADR-0006: compatibility strategy (additive-only, graceful degradation). |

### Phase 4: `@conversation` skill (recover lost Cascade feature)

| Task | Detail |
|---|---|
| 4.1 | Skill `.devin/skills/dcr-conversation/SKILL.md`: detect `@conversation: <title>` in prompt, call `dcr search`, inject summary. |
| 4.2 | Global rule: document the mechanism in `global_rules.md`. |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `sessions.db` schema changes on Devin Desktop update | D4: version detection + graceful degradation. `refinery` = additive migrations. |
| `main_chain_id` NULL or absent | Fallback: set `on_main_chain=0` for all nodes, rely on `created_at` ordering. No crash. |
| `node_id` not chronological (3705 inversions on 466 nodes) | Order steps by `created_at ASC, node_id ASC`, NOT `node_id` alone. |
| Duplicate tool results (`message_nodes` vs `tool_call_state`) | `message_nodes` is source of truth (more complete). `tool_call_state` (533 rows) ignored in Phase 1, used in Phase 2.1. |
| Lock contention on `sessions.db` (Devin Local writes during sync) | Open in `mode=ro` (read-only URI). |
| Performance: 102 sessions × 6056 nodes (full-tree, ~3.4× the main-chain volume) | SQLite → SQLite, batch insert, single transaction per session. FTS5 on `content_text` + `thinking` increases DB size but stays well within SQLite limits. |
| Full-tree volume: 62 % of nodes are lateral branches | Indexed (user wants abandoned responses for `cascade-self-config` diagnosis). `on_main_chain` flag keeps default views lean; `--full-tree` is opt-in (Phase 2.5). |
| Re-index Cascade for enrichment (Phase 1B) | `dcr sync --force` (new flag, Phase 1B.2). Optional — existing data stays valid. Phase 1B is deferrable/skippable. |

## Consequences

- **Positive**: `dcr` covers both Cascade (legacy) and Devin Local (future). No user-facing
  change to `sync`/`search`/`list`/`show`/`export`. Devin Local `thinking`/`tool_calls`
  captured for free in Phase 1A (JSON keys, no extra parsing). Full-tree indexing preserves
  regenerations and edited prompts — the signal needed for `cascade-self-config` diagnosis.
  Schema is future-proof for Devin Local evolution.
- **Negative**: schema migration required (idempotent, non-breaking). New module
  (`devin_local.py`) to maintain. Devin Local schema version must be monitored (Phase 3).
  Full-tree indexing increases DB size (~3.4× main-chain volume) and FTS5 index size.
- **Neutral**: `source_type` column adds a filter dimension but doesn't change existing
  queries (default = all sources). Cascade parser enrichment (Phase 1B) is deferred and
  skippable — it doesn't block Devin Local value.

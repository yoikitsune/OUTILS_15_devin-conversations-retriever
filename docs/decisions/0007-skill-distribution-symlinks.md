# ADR-0007: Skill Distribution via Symlinks

> Status: Accepted
> Date: 2026-08-02

## Context

ADR-0004 established a three-layer integration model for DCR:

1. **Discovery layer** — Global Rule (`~/.codeium/windsurf/memories/global_rules.md`) with `<dcr_tool_awareness>` and `<dcr_conversation_skill>` XML tags (~200 tokens permanent, all projects).
2. **Documentation layer** — `dcr --help` (0 tokens idle).
3. **Procedural layer** — `cascade-self-config` skill + `dcr-conversation` skill.

At the time, `dcr-conversation` was a **project skill** (lived in `<repo>/.devin/skills/`), only available when working inside the DCR repo. The global Rule was the only way to give cross-project awareness of DCR's existence. There was also no installation mechanism — the skill was discovered only because the agent's cwd was the DCR repo.

Two needs emerged, both tied to the same gap:

1. **Installation** — DCR (and any tooling project) needs a way to make its skills available globally: install, update, uninstall. There was no such mechanism. The skill was locked to its repo.
2. **Multi-project awareness** — A second tooling project (`cascade-self-config`) also ships global skills. If both projects put awareness in the same `global_rules.md`, they couple. The shared-file model breaks down: who owns the file? What happens on uninstall? How does it scale to N tools?

These two needs are **the same problem**: how does a tooling project expose its capabilities globally, cleanly, and reversibly? The answer to installation determines the answer to awareness. If skills can be installed globally and carry their own description (tier-1, ~100 tokens), the global Rule becomes redundant for awareness — and with it, the coupling problem disappears.

This ADR addresses both: the **installation mechanism** (primary decision) and the **global Rule removal** (consequence).

## Decision

**Distribute skills globally via symlinks. Each tooling project owns and manages its own symlinks via a portable install script. As a consequence, remove project-specific awareness from the global Rule — skills carry their own awareness via their tier-1 description.**

### Primary decision: symlink-based installation

1. **Skills are the unit of distribution.** Each tooling project ships its skills in `.devin/skills/<name>/SKILL.md` (version-controlled, single source of truth). The repo is the canonical location.

2. **Global installation creates symlinks** from the global skills directory to the repo's `.devin/skills/<name>/`. On Linux/macOS: `ln -s`. On Windows: `mklink /J` (junctions — no admin required, unlike symlinks). Both are followed by Devin's skill discovery (changelog v2026.5.6-1).

3. **`scripts/install-skills.sh` (Linux/macOS) and `scripts/install-skills.ps1` (Windows)** are the canonical install/update/uninstall commands. Each tooling project ships its own copy with its skill list in a config array at the top. Usage:
   ```
   ./scripts/install-skills.sh           # install (idempotent)
   ./scripts/install-skills.sh --remove  # uninstall
   ./scripts/install-skills.sh --list     # status
   ```

4. **Updates are live.** Editing `SKILL.md` in the repo immediately affects all sessions — no copy, no drift, no re-publish. `git pull` is the update mechanism.

5. **Uninstall removes the symlink only.** The repo is untouched. No stale copies, no orphan files.

6. **Target directory: `~/.codeium/windsurf/skills/`** (Windsurf channel, read by Devin via import). This is consistent with existing global skills (`cascade-self-config`, `evaluateur`) already installed there. The standard Devin path (`~/.config/devin/skills/`) is also valid but would split skills across two directories for no benefit.

7. **The pattern is general.** Any tooling project that ships skills (DCR, `cascade-self-config`, future tools) follows the same structure: `.devin/skills/<name>/` + `scripts/install-skills.{sh,ps1}`. No shared global file to edit when a project is added, removed, or updated.

### Consequence: global Rule removal

8. **Since skills are now global and carry their own awareness** (tier-1 description, ~100 tokens, loaded in every session), the `<dcr_tool_awareness>` and `<dcr_conversation_skill>` blocks in `~/.codeium/windsurf/memories/global_rules.md` are redundant. They are removed. If the file becomes empty, it is deleted.

9. **The global Rule (if it exists at all) should contain only genuine personal preferences** — the same role as `~/.codex/AGENTS.md` or `~/.claude/CLAUDE.md`. Tool-specific awareness does not belong there.

10. **`dcr --help` remains the documentation layer** (0 tokens idle, loaded on demand). The CLI is self-documenting.

11. **The two safety-critical warnings** that were in `<dcr_tool_awareness>` (auto-sync redundancy, ID confusion with `trajectory_search`) move to:
    - The `dcr-conversation` SKILL.md (already partially covered by the skill's procedure).
    - `dcr --help` output (already present for auto-sync; the ID confusion warning should be added to `dcr show --help` and `dcr export --help`).
    - The project `AGENTS.md` (for when working inside the DCR repo itself).

## Evidence

### 1. Vercel Labs Skills CLI: symlinks are the recommended distribution method

**Source**: [Vercel Labs Skills — installation methods](https://vercel-labs-skills.mintlify.app/guides/installation-methods)

> *"Symlink Mode (Recommended): Skills are copied to `.agents/skills/<name>/` (or `~/.agents/skills/<name>/` for global). Each agent's skill directory symlinks to the canonical location. Single source of truth, easy updates."*

> *"Benefits: Skills live in one canonical location. When you update a skill, all agents see the changes immediately. One copy on disk instead of multiple duplicates."*

**Source**: [DeepWiki — Symlink Installation](https://deepwiki.com/tech-leads-club/agent-skills/6.1-symlink-installation)

> *"The system automatically falls back to copy installation if symlink creation fails, ensuring skills are installed regardless of platform limitations or permissions."*

**Source**: [DeepWiki — Global vs Local Scope](https://deepwiki.com/tech-leads-club/agent-skills/6.3-global-vs-local-scope)

> *"Global scope installs skills to the user's home directory, making them available across all projects on the system."*

**Implication**: The symlink approach we adopted is the industry-recommended pattern. Canonical source in the repo, symlink in the global directory, live updates, fallback to copy on platforms where symlinks fail. Our `scripts/install-skills.{sh,ps1}` implements this pattern manually (without the Vercel CLI dependency).

### 2. Devin Desktop supports symlinked skill directories

**Source**: Devin CLI changelog (`docs/changelog/stable.mdx`, v2026.5.6-1)

> *"The in-session `skill` tool now finds skills behind symlinked directories under `.windsurf/skills/`, `.agents/skills/`, and `.claude/skills/`, matching `devin skills list`."*

**Source**: Devin CLI plugins doc (`docs/extensibility/plugins/overview.mdx`)

> *"Local plugins are linked directly to their source folder, so edits are live: `devin plugins install ./my-plugin` → edit `skills/<name>/SKILL.md` → changes apply on the next session, no `update` needed."*

**Implication**: Devin's own plugin system uses the same link-based live-edit model. Our symlink approach is consistent with how Devin itself thinks about local installations. Validated empirically: `devin skills list` from `/tmp` (outside the DCR repo) shows `/dcr-conversation` resolving through the symlink.

### 3. Devin Desktop recommends skills over rules for discovery

**Source**: Devin CLI docs (`docs/extensibility/rules.mdx`)

> *"To improve coding ability, speed of completion, and lower cost, we highly recommend using Skills instead whenever possible. Skills are only injected into the context when relevant. Rules and AGENTS should be kept as small as possible."*

> *"Our recommended pattern is to use a rule to reference skills that the model should use in particular scenarios."*

**Source**: Devin CLI docs (`docs/extensibility/skills/overview.mdx`)

Global skills are supported at `~/.config/devin/skills/`, `~/.agents/skills/`, and `~/.codeium/<channel>/skills/` (the latter read via Windsurf import). Skills carry their own awareness via their `description` frontmatter (tier-1, ~100 tokens).

**Implication**: Devin's own guidance aligns with the industry consensus — skills for discovery, rules kept minimal. A ~200-token `<dcr_tool_awareness>` block in a global Rule is heavier than what Devin recommends, and redundant once the skill is global.

### 4. The AGENTS.md standard separates global (personal) from project (specific)

**Source**: [agents.md](https://agents.md/) (Linux Foundation Agentic AI Foundation)

> *"AGENTS.md complements this by containing the extra, sometimes detailed context coding agents need: build steps, tests, and conventions that might clutter a README or aren't relevant to human contributors."*

The standard's mental model: global = personal preferences, project = project conventions. There is no standard mechanism for "a tooling project publishes awareness into the user's global file."

### 5. Codex explicitly warns against project-specific content in the global file

**Source**: [OpenAI Codex — AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)

> *"The key insight: global AGENTS.md defines personal standards, not project specifics. Project specifics go in the repo."*

> *"Project-specific instructions in the global file add noise for every project and can conflict with instructions in a project's own AGENTS.md. Every byte in `~/.codex/AGENTS.md` is a byte that cannot be used by project-level files."*

**Implication**: `<dcr_tool_awareness>` in a global Rule is exactly the "project-specific instructions in the global file" anti-pattern. It taxes every project's context with DCR-specific details, even projects that will never use `dcr`.

### 6. Claude Code: skills carry their own awareness, not CLAUDE.md

**Source**: [Claude Code — memory](https://code.claude.com/docs/en/memory.md)

> *"Keep it to facts Claude should hold in every session: build commands, conventions, project layout, 'always do X' rules. If an entry is a multi-step procedure or only matters for one part of the codebase, move it to a skill or a path-scoped rule instead."*

**Source**: [Claude Code — skills](https://code.claude.com/docs/en/skills)

> *"Create a skill when you keep pasting the same instructions, checklist, or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact. Unlike CLAUDE.md content, a skill's body loads only when it's used, so long reference material costs almost nothing until you need it."*

Claude Code's global `~/.claude/CLAUDE.md` (~320 tokens) is for personal preferences. Skills (`~/.claude/skills/<name>/SKILL.md`) carry their own awareness via their description. **No project-specific tool awareness lives in the global CLAUDE.md.**

### 7. Cursor: global "Rules for AI" is a single personal baseline, not a per-project registry

**Source**: [Cursor docs — rules](https://cursor.com/docs/rules.md)

Cursor's global rules ("Rules for AI") live in user settings, are a single file, and contain personal baseline preferences. Project rules live in `.cursor/rules/*.mdc` (version-controlled, scoped by globs). **There is no mechanism for a tooling project to "register" awareness in the global Rules for AI.** Each project manages its own rules locally.

### 8. Multi-project coupling is the core problem with the shared-file model

The original global Rule was written when DCR was the only tooling project. Now that `cascade-self-config` also ships global skills, the shared-file model breaks down:

- **Ownership**: Who owns `global_rules.md`? Neither repo versions it. Edits are manual, untracked, unrevertable.
- **Lifecycle**: If DCR is uninstalled, the `<dcr_tool_awareness>` block becomes stale and must be manually removed from a file the DCR repo doesn't control. With symlinks, uninstall removes the link — nothing else to clean up.
- **Scaling**: Each new tooling project would append another `<..._awareness>` block, growing the global Rule unboundedly. N projects × ~100 tokens = N×100 tokens of permanent context tax on every session. With per-skill awareness, the cost is the same N×100 tokens but each token is attached to a skill that can be individually uninstalled.
- **Conflicts**: Two projects could write contradictory guidance into the same file.

The symlink-per-skill model has none of these problems: each project owns its skills, installation/removal is one command per project, and the context cost scales with actually-installed skills.

## Rationale

### On symlink-based installation

- **Single source of truth**: The repo is canonical. The global directory holds a link. No copy drift, no two places to edit.
- **Live updates**: `git pull` → next session sees the updated skill. No re-install step for content changes. This matches the Vercel Labs recommended pattern and Devin's own plugin link model.
- **Clean uninstall**: Remove the symlink. The repo is untouched. No stale copies in the global directory.
- **Cross-platform**: Linux/macOS use `ln -s` (standard symlinks). Windows uses `mklink /J` (junctions — no admin required). Both are followed by Devin's skill discovery. The Windows behavior is not officially documented but junctions are followed by Node.js `fs.realpath`, which Devin uses.
- **No external dependency**: The install scripts are plain Bash/PowerShell. No need for the Vercel Labs Skills CLI or any package manager. Each tooling project is self-contained.
- **General pattern**: Any tooling project can adopt this by copying the two scripts and editing the skill list array. The structure (`.devin/skills/` + `scripts/install-skills.{sh,ps1}`) is reproducible.

### On global Rule removal (consequence)

- **Skills are self-describing**: A skill's `description` frontmatter is loaded at tier-1 (~100 tokens) in every session and tells the agent when to invoke the skill. This is exactly the "awareness" job that `<dcr_tool_awareness>` was doing manually — but standardized, per-skill, and removable by uninstalling the skill.
- **No cross-project coupling**: DCR, `cascade-self-config`, and future tools each ship their own skills and install scripts. Adding/removing a tooling project is a single symlink operation, not an edit to a shared file.
- **Global Rule stays clean**: The global Rule (if it exists at all) should contain only genuine personal preferences — the same role as `~/.codex/AGENTS.md` or `~/.claude/CLAUDE.md`. Tool-specific awareness does not belong there.
- **Cost is lower**: Removing `<dcr_tool_awareness>` (~150 tokens) and `<dcr_conversation_skill>` (~50 tokens) saves ~200 tokens/session. The skill description (~100 tokens) replaces them. Net saving: ~100 tokens/session, with better isolation.
- **Safety warnings are preserved**: The two non-obvious warnings (auto-sync, ID confusion) move to `dcr --help` output and the `dcr-conversation` SKILL.md, where they are loaded only when relevant — not permanently in every session.

## Alternatives Considered

### For installation

- **Copy-based installation** (cp the skill directory to the global location): Rejected. Creates a second copy that drifts from the repo. Updates require re-running install. Uninstall leaves potential stale copies. The Vercel Labs CLI uses copy only as a fallback when symlinks fail, not as the primary method.

- **Devin plugins** (`devin plugins install ./repo`): Considered. Plugins are Devin's official install/update/uninstall system, and local plugins are linked (live edits). However, plugins are in **closed beta** (requires contacting `support@cognition.ai`). The plugin structure (`.devin-plugin/plugin.json` + `skills/`) is a superset of what we have, so migration is possible later. For now, symlinks are the pragmatic choice that works today. When plugins go GA, the repo can add a `.devin-plugin/plugin.json` and the install scripts can delegate to `devin plugins install`.

- **Vercel Labs Skills CLI** (`npx skills install`): Considered. Implements the symlink pattern we want, with global/local scope and multi-agent support. But adds an external Node.js dependency and a canonical copy at `~/.agents/skills/` (introducing a third location alongside the repo and the global skills dir). Our manual scripts are simpler and keep the repo as the sole canonical source. If we later want multi-agent support (Claude Code, Cursor, Codex from one install), the Vercel CLI becomes attractive — but that's a future concern, not today's.

- **No installation, keep skills project-only**: Rejected. DCR's value proposition is cross-project conversation retrieval. A skill that only works inside the DCR repo defeats the purpose.

### For global Rule removal

- **Keep the global Rule as-is**: Rejected. Project-specific content in a global shared file is the anti-pattern identified by Codex, Claude Code, and Cursor docs. Coupling between DCR and `cascade-self-config` (and future tools) would grow unboundedly.

- **Split the global Rule into per-project files** (e.g., `~/.codeium/windsurf/memories/dcr_rules.md`, `~/.codeium/windsurf/memories/cascade-self-config_rules.md`): Rejected. Devin/Windsurf reads a single `global_rules.md` (or `AGENTS.md`), not a directory of per-project files. This would require a non-standard loader. And it still taxes every session with every project's awareness, even when that project isn't relevant.

- **Keep `<dcr_tool_awareness>` but remove `<dcr_conversation_skill>`** (partial trim): Rejected. The `<dcr_tool_awareness>` block is the larger offender (~150 tokens of project-specific content in a global file). Removing only the smaller block doesn't solve the coupling problem. If the skill description suffices for `@conversation`, it suffices for the CLI too — the CLI is documented by `--help` and the skill.

- **Migrate the global Rule to `~/.config/devin/AGENTS.md`** (standard Devin path): Partially accepted as a future direction. If a global Rule is kept for personal preferences, it should follow the standard path rather than the Windsurf-legacy path. But this ADR's decision is to **remove project-specific content from the global Rule**, not to migrate its location. Location migration is a separate concern.

- **Use a separate global skill for CLI awareness** (e.g., a `dcr-cli` skill whose description says "dcr is a CLI for conversation retrieval, run `dcr --help`"): Considered, rejected as over-engineering for now. The `dcr-conversation` skill already covers the main use case (`@conversation`). If pure CLI awareness (without the `@conversation` framing) becomes needed, a minimal `dcr-cli` skill can be added later — it would follow the same symlink distribution model.

## Consequences

### Installation

- **`scripts/install-skills.sh` and `scripts/install-skills.ps1`**: Created. These are the canonical install/uninstall/list commands for exposing DCR skills globally. Each tooling project that wants global skills should ship its own copy with its skill list.
- **`dcr-conversation` skill**: Now global via symlink at `~/.codeium/windsurf/skills/dcr-conversation/`. Available in all projects. Empirically validated via `devin skills list` from `/tmp`.
- **Windows support**: Junctions (`mklink /J`) are used instead of symlinks (`mklink /D`) to avoid the admin/Developer Mode requirement. Windows behavior is not officially documented by Devin but is expected to work (Node.js `fs.realpath` follows junctions). To be validated empirically on a Windows machine.
- **Future migration to Devin plugins**: When plugins go GA, the repo can add `.devin-plugin/plugin.json` and the install scripts can delegate to `devin plugins install ./repo`. The symlink approach is forward-compatible — the plugin structure is a superset of the current layout.

### Global Rule removal

- **`~/.codeium/windsurf/memories/global_rules.md`**: The `<dcr_tool_awareness>` and `<dcr_conversation_skill>` blocks are removed. If the file becomes empty, it is deleted. If it contains other personal preferences, those remain.
- **`dcr --help`**: The auto-sync warning is already present. The ID confusion warning (`trajectory_search` expects Cascade UUID, not numeric dcr id) should be added to `dcr show --help` and `dcr export --help` output.
- **`dcr-conversation/SKILL.md`**: Should include the two safety warnings (auto-sync, ID confusion) in its procedure, since it is now the primary entry point for DCR usage from other projects.

### ADR-0004 amendment

The "three-layer model" in ADR-0004 is revised:

1. **Discovery layer** — ~~Global Rule~~ → **Skill description (tier-1)**, loaded in every session via the globally-installed skill. ~100 tokens/skill, removable by uninstalling the skill.
2. **Documentation layer** — `dcr --help` (unchanged).
3. **Procedural layer** — `dcr-conversation` skill + `cascade-self-config` skill (unchanged, but now globally installed via symlinks).

This ADR supersedes the "Discovery layer — Global Rule" bullet of ADR-0004's Consequences section.

### Future tooling projects

Should follow the same pattern:
- Ship skills in `.devin/skills/<name>/`
- Ship `scripts/install-skills.{sh,ps1}` with the skill list
- Do not write to a shared global Rule
- Uninstall = remove symlinks (one command)

---

## Amendment 2026-08-02: Skill + CLI companion distribution

> Supersedes bullet 1 of the Primary decision ("Skills are the unit of distribution") and the empirical validation claim in Consequences ("Empirically validated via `devin skills list` from `/tmp`").

### Bug discovered

The original ADR scoped the unit of distribution as **the skill alone**. This is correct for skills that are pure procedures (markdown only). It is **incorrect** for skills that wrap an external CLI: a skill that documents `dcr search ...` is useless if `dcr` is not on PATH.

This bug was caught by conversation `marked-cotton` (2026-08-02): from a non-DCR project (`cascade-self-config`), the `dcr-conversation` skill was correctly invoked (proving the symlink works), but the skill's documented command `dcr search ...` failed with `bash: dcr: commande introuvable`. The model then attempted `find / -name "dcr"` — a full filesystem scan — to locate the binary. The user interrupted.

Root cause: the skill was **discoverable everywhere but functional nowhere outside the DCR repo**. The CLI `dcr` lives only at `repo/.venv/bin/dcr` (not on PATH). The original empirical validation (`devin skills list` from `/tmp`) only checked **discovery**, not **end-to-end functionality**.

### Corrected decision

**The unit of distribution is the skill + its CLI companion.** When a skill wraps a CLI, the install script must expose both globally:

1. **Skill** → symlink in `~/.codeium/windsurf/skills/<name>/` (unchanged).
2. **CLI companion** → wrapper script in `~/.local/bin/<binary>` that `exec`s the repo's venv binary. The wrapper resolves its own symlink to find the real binary, so it stays valid regardless of where `~/.local/bin/<binary>` is invoked from.

The wrapper (not `pipx install`) is used because `pipx` copies the project into an isolated venv, which **breaks live edits** — a core requirement of this ADR (bullet 4: "git pull is the update mechanism"). The wrapper pattern preserves the repo as the single source of truth.

### Why not embed the CLI in the skill's `scripts/`

The agentskills.io spec defines an optional `scripts/` directory for executable code shipped with the skill. This is the right pattern for **self-contained scripts** (bash, autonomous Python). It does not fit `dcr`: the CLI is a Python package with non-trivial dependencies (`cryptography`, `protobuf`, FTS5). Embedding it in `scripts/` would require either vendoring the deps or re-implementing the venv setup inside the skill — both worse than the wrapper approach. The spec's `scripts/` convention is cited here for completeness, not as the chosen mechanism.

### Evidence

- **[enact/link-enact.sh](https://github.com/EnactProtocol/enact/blob/main/scripts/link-enact.sh)**: build CLI → create wrapper script → symlink into `~/.local/bin/`. Wrapper resolves its own symlink to find the real script, then `exec`s it. Live edits preserved, uninstall = `rm` the symlink. This is exactly our pattern, adapted from Node/bun to Python.
- **[AdebayoBraimah/install-local-skills](https://github.com/adebayobraimah/install-local-skills)**: `install-skills.sh` runs in **multiple phases** — agent skills, MCP servers, **pip packages via `uv pip install`**, Claude plugins. Coupling "install skills" with "install companion CLI/packages" in the same script is an established pattern, not a hack.
- **[skillsmith](https://github.com/Songmu/skillsmith)**: a Go CLI that **embeds its skills** via `embed.FS` and exposes `mytool skills install`. The inverse of our pattern (CLI ships skills, vs. skill ships CLI), but the same principle: **skill and its executable are co-distributed as one unit**. Splitting them creates a broken state.
- **[pipx](https://pipx.pypa.io/latest/explanation/how-pipx-works/)**: the canonical Python pattern for global CLI install (`pipx install /path/to/project` → isolated venv + symlink in `~/.local/bin`). **Rejected here** because pipx copies the project into an isolated venv, breaking live edits. Cited as the reference for the `~/.local/bin` target convention.

### Corrected empirical validation

The original validation (`devin skills list` from `/tmp`) only proves **discovery**. The corrected validation must prove **end-to-end functionality**:

```bash
cd /tmp
devin skills list | grep dcr-conversation          # discovery (unchanged)
~/.local/bin/dcr search "test"                     # CLI companion is on PATH
dcr search "test"                                  # CLI is on PATH (no absolute path needed)
```

All three must pass from a directory that is **not** the DCR repo. If the third fails, the install is incomplete — the skill is discoverable but not functional.

### SKILL.md fallback

The `dcr-conversation` SKILL.md must document the absolute path to the binary as a fallback, in case the wrapper is missing (e.g., user ran `install-skills.sh` before the wrapper phase was added). The fallback is:

```bash
/home/julien/Sources/devin-conversations-retriever/.venv/bin/dcr <command>
```

Additionally, the SKILL.md must include an explicit rule: **never run `find /` to locate a binary**. If `dcr` is not on PATH and the absolute fallback is missing, ask the user to re-run `./scripts/install-skills.sh`. A full filesystem scan is never the right answer.

### Updated install script contract

`scripts/install-skills.sh` and `scripts/install-skills.ps1` now have two phases:

1. **Skills phase** — symlink each skill in `SKILLS[]` into `~/.codeium/windsurf/skills/` (unchanged).
2. **CLI phase** — for each entry in `CLI_BINARIES[]` (name + path to repo venv binary), create a wrapper script in `~/.local/bin/<name>` that `exec`s the venv binary. Idempotent: re-running replaces the wrapper if the target path changed.

`--remove` removes both skill symlinks and CLI wrappers. `--list` shows both. The config array `CLI_BINARIES[]` is empty for tooling projects that ship pure-procedure skills (e.g., `cascade-self-config`); it is populated only when a skill wraps a CLI.

## Sources

| # | Source | URL | Key point |
|---|---|---|---|
| 1 | Vercel Labs Skills — installation | https://vercel-labs-skills.mintlify.app/guides/installation-methods | Symlink is recommended mode. Canonical source + symlinks per agent. |
| 2 | DeepWiki — Symlink Installation | https://deepwiki.com/tech-leads-club/agent-skills/6.1-symlink-installation | Auto-fallback to copy if symlinks fail. Live updates. |
| 3 | DeepWiki — Global vs Local Scope | https://deepwiki.com/tech-leads-club/agent-skills/6.3-global-vs-local-scope | Global scope = user home dir, available across all projects. |
| 4 | Devin CLI — changelog v2026.5.6-1 | `docs/changelog/stable.mdx` | "skill tool now finds skills behind symlinked directories." |
| 5 | Devin CLI — plugins overview | `docs/extensibility/plugins/overview.mdx` | Local plugins are linked, edits are live. Closed beta. |
| 6 | Devin CLI — rules | `docs/extensibility/rules.mdx` | "Use Skills instead whenever possible. Rules kept as small as possible." |
| 7 | Devin CLI — skills overview | `docs/extensibility/skills/overview.mdx` | Global skills at `~/.config/devin/skills/` or `~/.codeium/<channel>/skills/`. |
| 8 | AGENTS.md standard | https://agents.md/ | Global = personal prefs, project = project conventions. No per-project awareness in global. |
| 9 | OpenAI Codex — AGENTS.md guide | https://developers.openai.com/codex/guides/agents-md | "Project-specific instructions in the global file add noise for every project." ~100 lines max for global. |
| 10 | Claude Code — memory | https://code.claude.com/docs/en/memory.md | Global CLAUDE.md = personal prefs. "Move procedures to a skill." |
| 11 | Claude Code — skills | https://code.claude.com/docs/en/skills | Skills carry their own awareness via description. Global skills at `~/.claude/skills/`. |
| 12 | Cursor — rules | https://cursor.com/docs/rules.md | Global "Rules for AI" = single personal baseline. No per-project registry in global. |
| 13 | AgentPatterns — distributed AGENTS.md | https://agentpatterns.ai/instructions/agents-md-distributed-conventions/ | Global agent config = multi-repo context (where repos live), not per-tool awareness. |
| 14 | EnactProtocol — link-enact.sh | https://github.com/EnactProtocol/enact/blob/main/scripts/link-enact.sh | Wrapper script + symlink in `~/.local/bin`. Wrapper resolves its own symlink, `exec`s the real binary. Live edits preserved. |
| 15 | AdebayoBraimah — install-local-skills | https://github.com/adebayobraimah/install-local-skills | Multi-phase `install-skills.sh`: skills + MCP servers + pip packages. Coupling skill install with companion CLI install is established. |
| 16 | Songmu — skillsmith | https://github.com/Songmu/skillsmith | Go CLI embeds its skills via `embed.FS`, exposes `mytool skills install`. Skill + executable co-distributed as one unit. |
| 17 | pipx — how it works | https://pipx.pypa.io/latest/explanation/how-pipx-works/ | Canonical Python pattern: isolated venv + symlink in `~/.local/bin`. Rejected here (breaks live edits), cited for the `~/.local/bin` target convention. |
| 18 | agentskills.io — specification | https://agentskills.io/specification | Skill structure: `SKILL.md` + optional `scripts/`. `scripts/` is for self-contained executable code, not for wrapping external CLIs with deps. |

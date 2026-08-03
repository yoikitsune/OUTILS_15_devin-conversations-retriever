# ADR-0008: Migration to XDG-Convention Skill Paths

> Status: Accepted
> Date: 2026-08-03

## Context

ADR-0007 established the symlink-based skill distribution pattern. At the time (2026-08-02), the target directory was `~/.codeium/windsurf/skills/` — the Windsurf channel path, read by Devin via import.

Since then, two things changed:

1. **Cascade reached end-of-life on 2026-07-01**, replaced by Devin Local (Rust rewrite). The `~/.codeium/windsurf/` path is a Cascade-era legacy path. Devin Local's canonical skill paths are documented at `https://docs.devin.ai/cli/extensibility/skills`:
   - `~/.config/devin/skills/` (XDG-convention, Linux/macOS)
   - `%APPDATA%\devin\skills\` (Windows)
   - `~/.agents/skills/` (standard cross-agent `.agents`)

2. **The `devin-self-config` project (formerly `cascade-self-config`) already migrated** to the XDG path via its ADR-0002 (2026-08-02). Its `install-skills.{sh,ps1}` were updated with a `cleanup_legacy_skill` / `Cleanup-Legacy-Skill` function that automatically removes stale installations from `~/.codeium/windsurf/skills/`. DCR's scripts remained on the old path, creating an inconsistency: `devin-self-config` installs at `~/.config/devin/skills/` but `dcr-conversation` (its dependency) installs at `~/.codeium/windsurf/skills/`.

This ADR aligns DCR with the new canonical path and the `devin-self-config` project.

## Decision

**Migrate the global skill installation path from `~/.codeium/windsurf/skills/` to `~/.config/devin/skills/` (Linux/macOS) and `%APPDATA%\devin\skills\` (Windows). Add automatic cleanup of legacy installations.**

### Concrete changes

1. **`install-skills.sh`** — `GLOBAL_SKILLS_DIR` changed from `${HOME}/.codeium/windsurf/skills` to `${HOME}/.config/devin/skills`. Added `LEGACY_SKILLS_DIRS` array and `cleanup_legacy_skill()` function (adapted from `devin-self-config`'s script). `unlink_skill` and `list_skill` extended to handle legacy paths.

2. **`install-skills.ps1`** — `$GlobalSkillsDir` changed from `%USERPROFILE%\.codeium\windsurf\skills` to `%APPDATA%\devin\skills`. Added `$LegacySkillsDirs` array and `Cleanup-Legacy-Skill` function. `Unlink-Skill` and `List-Skill` extended.

3. **CLI wrapper (`~/.local/bin/dcr`) is unaffected** — it lives in `~/.local/bin/` regardless of the skill path. The CLI phase of the install script is unchanged.

4. **Cleanup is automatic** — running `install-skills.sh` (or `.ps1`) at the new path will detect and remove any stale symlink/junction at the old path. No manual cleanup needed.

### What changes vs ADR-0007

| Aspect | ADR-0007 (2026-08-02) | ADR-0008 (2026-08-03) |
|---|---|---|
| Linux/macOS path | `~/.codeium/windsurf/skills/` | `~/.config/devin/skills/` |
| Windows path | `%USERPROFILE%\.codeium\windsurf\skills\` | `%APPDATA%\devin\skills\` |
| Legacy cleanup | No | Yes (automatic) |
| Principle | Symlink distribution | Unchanged — only the path changes |

## Consequences

- **Positives**:
  - Canonical XDG path — aligned with Devin CLI documentation
  - Consistency with `devin-self-config` (both projects use the same path)
  - Automatic cleanup — no stale symlinks left in the old path
  - Forward-compatible — `~/.config/devin/` is the standard location for Devin configuration

- **Necessary**:
  - Users with an existing install at the legacy path must re-run `install-skills.sh` (or `.ps1`) — the script handles the migration automatically (cleanup + new symlink)
  - The CLI wrapper at `~/.local/bin/dcr` does not need reinstallation

## Evidence

- **Devin CLI Skills docs** : `https://docs.devin.ai/cli/extensibility/skills` — canonical paths `~/.config/devin/skills/`, `~/.agents/skills/`
- **devin-self-config ADR-0002** : `/home/julien/Sources/cascade-self-config/docs/decisions/0002-migrate-cascade-to-devin-local.md` — same migration, already applied and validated
- **Devin Desktop launch** : `https://devin.ai/blog/windsurf-is-now-devin-desktop` (2 juin 2026) — Cascade EOL, Devin Local replacement

## Relations

- **Amends** : ADR-0007 (skill distribution via symlinks — the principle is unchanged, only the target path moves)
- **Aligns with** : `devin-self-config` ADR-0002 (same migration, applied 2026-08-02)
- **Supersedes** : the `~/.codeium/windsurf/skills/` path from ADR-0007

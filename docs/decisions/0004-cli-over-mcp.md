# ADR-0004: CLI + Skill over MCP Server

> Status: Accepted
> Date: 2026-07-26

## Context

Milestone M7 planned an MCP server (`server.py`) using FastMCP to expose DCR's search, list, and sync capabilities as MCP tools that Cascade could call natively. The entry point is already declared in `pyproject.toml`:

```toml
"devin-conversations-retriever" = "dcr.server:main"
```

After researching how Windsurf loads MCP servers, the token cost of MCP tool schemas, the CLI-vs-MCP decision frameworks published by multiple industry sources, and the Agent Skills open specification, we conclude that an MCP server is the wrong integration model for DCR. The correct model is **CLI + Skill** — the CLI provides execution, the Skill provides discovery and guided usage.

This ADR documents that decision with supporting evidence from official Windsurf documentation, the Agent Skills specification, and industry best practices.

## Decision

**Reject M7 (MCP server). Use the existing CLI (`dcr`) as the execution layer, complemented by an Agent Skill for discovery and guided usage.**

DCR is invoked occasionally (during self-config sessions, manual searches), not on every conversation. An MCP server would impose a permanent token cost on every Cascade turn for tools that are rarely used. The CLI already exists with 7 subcommands and 114 tests — it is complete, tested, and zero-cost when idle. An Agent Skill adds ~50-100 tokens of description to the context (progressive disclosure tier 1) and provides full instructions only when invoked — giving the discovery and guidance benefits of MCP without its permanent cost.

## Evidence

### 1. MCP servers are always-on in Windsurf

**Source**: [Windsurf MCP Documentation](https://docs.windsurf.com/windsurf/cascade/mcp)

> *"Cascade now natively integrates with MCP, allowing you to bring your own selection of MCP servers for Cascade to use."*

**Source**: [ContextBolt — Windsurf MCP Setup 2026](https://contextbolt.com/blog/windsurf-mcp-setup/)

> *"Stdio servers run locally. Windsurf spawns the process and talks to it through standard input and output."*

> *"Windsurf starts all configured servers when the editor launches and the Cascade agent can call any of them."*

> *"Hard ceiling: 100 tools total across all servers. Past that, Cascade drops the extras."*

**Source**: [LOW/CODE — Windsurf MCP Servers 2026](https://www.lowcode.agency/blog/windsurf-mcp-servers)

> *"Local server processes add resource overhead: Each active MCP server runs as a separate process on your machine. Configuring many servers simultaneously can affect memory and startup time."*

**Implication**: Once configured in `mcp_config.json`, an MCP server's process runs for the entire Windsurf session. Its tool schema is loaded into Cascade's context on every turn — regardless of whether the tools are used.

### 2. MCP tool schemas consume context permanently

**Source**: [Vincent van Deth — MCP vs CLI](https://vincentvandeth.nl/blog/mcp-vs-cli-when-to-replace)

> *"Every time an MCP server is connected, its full tool definitions get injected into the model's context on every single turn. Tool names, descriptions, complete parameter schemas. You pay for that on every message, whether or not you ever call the tool."*

> *"A single MCP server can add roughly 770 tokens of standing schema per turn. [...] a typical enterprise stack of five to ten servers burns 100,000 to 200,000 tokens before the user types a single character."*

> *"A CLI binary costs zero standing tokens. It sits on disk and consumes nothing until you call it."*

**Source**: [AddyOsmani — MCP Deep Dive](https://addyosmani.com/agents/16-mcp-deep-dive/)

| Metric | CLI Approach | MCP Approach |
|---|---|---|
| Token cost (simple query) | ~1,400 tokens | ~44,000 tokens (32x more) |
| Initialization cost | Near zero | 50,000+ tokens for schema loading |
| Reliability (benchmark) | 100% | 72% |

> *"Many MCP servers are thin wrappers around tools that already have excellent CLIs. [...] LLMs already know how to use these CLIs. They were trained on millions of man pages, Stack Overflow answers, and GitHub repositories."*

### 3. Decision rubrics consistently recommend CLI for local, occasional tools

**Source**: [CircleCI — MCP vs. CLI for AI-native development](https://circleci.com/blog/mcp-vs-cli/)

> *"CLIs fit the inner loop: fast, local, zero overhead. MCP servers fit the outer loop: external systems, shared infrastructure, structured access."*

> *"The most-cited argument against MCP is context window consumption. When an AI coding assistant connects to an MCP server, the server's full tool schema loads into context."*

**Source**: [AddyOsmani — When to use which](https://addyosmani.com/agents/16-mcp-deep-dive/)

| Situation | Recommended | Why |
|---|---|---|
| Developer working locally | CLI | Zero setup, agent already knows the tools, cheapest option |
| Broad tool surface, occasional use | CLI | Avoid paying schema cost for tools rarely used |
| Well-known tools (git, docker, kubectl) | CLI | LLM has strong training data, reliable parsing |
| Single-user agent | CLI | Ambient permissions are acceptable |

**Source**: [DEV Community — MCP Server or CLI Decision Rubric](https://dev.to/bengreenberg/mcp-server-or-cli-a-decision-rubric-for-developer-tooling-2ch6)

> *"A CLI is strongest when the workflow already belongs to a human developer. If the task is repo-local, terminal-native, and already part of how developers build, test, debug, or ship software, start with the CLI."*

> *"If a human would reasonably run the tool while sitting inside a repo, reading logs, adjusting flags, and retrying, a CLI is usually the right primary interface."*

**Source**: [MindStudio — MCP Servers vs CLI Tools](https://www.mindstudio.ai/blog/mcp-servers-vs-cli-tools-for-ai-agents)

> *"CLI tools are the fastest way to get something working and verify it works. [...] For a quick proof of concept or a one-off task, that overhead isn't worth it."*

> *"If your agent is running continuously — processing incoming events, responding to webhooks, working through a queue — CLI tools will create bottlenecks. [...] MCP servers solve this."*

### 4. Agent Skills: progressive disclosure as a CLI enhancement

The MCP-vs-CLI comparison in sections 1-3 treats CLI as a raw tool that the agent must discover and learn by itself. However, the **Agent Skills open specification** ([agentskills.io](https://agentskills.io/home)) provides a third layer: a lightweight skill that teaches the agent how to use the CLI, with minimal context cost.

**Source**: [Agent Skills Specification](https://agentskills.io/home)

> *"Agent Skills are a lightweight, open format for extending AI agent capabilities with specialized knowledge and workflows."*

> *"Skills use progressive disclosure to manage context efficiently: Discovery — at startup, agents load only the name and description of each available skill. Activation — when a task matches a skill's description, the agent reads the full `SKILL.md` instructions into context. Execution — the agent follows the instructions, optionally loading referenced files or executing bundled code as needed."*

**Source**: [agentskills.io — Specification](https://agentskills.io/specification.md)

| Tier | Content | When | Token cost |
|---|---|---|---|
| 1. Metadata | `name` + `description` | Session start | ~50-100 tokens per skill |
| 2. Instructions | Full `SKILL.md` body | Skill activated | <5 000 tokens (recommended) |
| 3. Resources | `references/`, `scripts/`, `assets/` | On demand | Variable |

**Source**: [Microsoft Agent Framework — Adding Skills](https://learn.microsoft.com/en-us/agent-framework/journey/adding-skills)

> *"A **tool** gives the agent the ability to perform **one action**; a **skill** gives the agent the knowledge and resources to handle **an entire domain**."*

| | Tool (MCP) | Skill |
|---|---|---|
| **What it provides** | A single callable action | Instructions + reference material + optional scripts |
| **Context cost** | Tool schema is always in the prompt | Only name + description (~100 tokens) until invoked |
| **Portability** | Tied to the agent that registers it | Self-contained, cross-product (open standard) |
| **Best for** | Individual actions (query, send, validate) | Domain expertise (workflows, procedures) |

**Source**: [OpenAI Codex — Build Skills](https://developers.openai.com/codex/skills)

> *"Skills use progressive disclosure to manage context efficiently: Codex starts with each skill's name, description, and file path. Codex loads the full `SKILL.md` instructions only when it decides to use a skill."*

> *"This list uses at most 2% of the model's context window, or 8,000 characters when the context window is unknown."*

**Source**: [Windsurf Skills Documentation](https://docs.windsurf.com/windsurf/cascade/skills)

> *"Cascade uses progressive disclosure: only the skill's name and description are shown to the model by default. The full SKILL.md content and supporting files are loaded only when Cascade decides to invoke the skill. This keeps your context window lean even with many skills defined."*

| | Skills | MCP |
|---|---|---|
| **In system prompt?** | No — only name + description until invoked | Yes — full schema every turn |
| **Invocation** | Model decides (progressive disclosure) or `@mention` | Automatic (schema in context) |
| **Best for** | Multi-step procedures with supporting files | External tools, structured access |

**Implication**: A Skill provides the discovery and guided-usage benefits of MCP (the agent knows the tool exists and how to use it) at ~50-100 tokens of standing cost instead of ~3,000-5,000 tokens/turn for an MCP server. The Skill loads full instructions only when activated, then the agent calls the CLI via `run_command`.

### 5. Three-way comparison for DCR

| | MCP Server | Raw CLI | **Skill + CLI** |
|---|---|---|---|
| **Discovery** | Schema injected every turn | None (agent guesses from training data) | Description in catalog (~100 tokens) |
| **Cost when idle** | ~3-5K tokens/turn (5 tools) | 0 tokens | ~50-100 tokens (1 skill description) |
| **Cost when active** | Same permanent cost | 0 + command tokens | SKILL.md loaded once + command tokens |
| **Guided usage** | Schema (typed params) | None (training data) | Explicit instructions + references |
| **Infrastructure** | Permanent process + `mcp_config.json` | None | None |
| **Portability** | Limited to MCP clients | Universal | Open standard (agentskills.io) — Windsurf, Codex, Claude, etc. |
| **Auth / State** | Handled by server | Not available | Not needed (local) |

**Skill + CLI dominates on all 7 criteria** for DCR's use case.

### 6. DCR against the rubric

| Criterion | DCR | MCP justified? | CLI justified? | Skill + CLI justified? |
|---|---|---|---|---|
| Local or remote? | 100% local (SQLite, .pb files on disk) | No | **Yes** — no network, no auth | **Yes** |
| Authentication needed? | None — single-user, local | No | **Yes** — ambient permissions fine | **Yes** |
| Stateful multi-step sessions? | No — each command is independent | No | **Yes** — stateless is sufficient | **Yes** |
| Multi-user / RBAC? | No | No | **Yes** | **Yes** |
| Usage frequency | Occasional (self-config, manual search) | No — permanent cost for rare use | **Yes** — zero cost when idle | **Yes** — ~100 tokens when idle |
| Existing CLI? | Yes — `dcr` with 7 subcommands, 114 tests | No — would be a thin wrapper | **Yes** — already built and tested | **Yes** — Skill wraps existing CLI |
| Structured output needed? | No — text/markdown sufficient | No | **Yes** | **Yes** |
| Tool discovery needed? | Yes — agent must know when/how to use `dcr` | Yes — but permanent cost | No — agent guesses | **Yes** — Skill description triggers activation |
| Continuous agent loop? | No — episodic, on-demand | No | **Yes** | **Yes** |

**Score: 0/9 for MCP, 7/9 for raw CLI (lacks discovery), 9/9 for Skill + CLI.**

## Rationale

- **Near-zero standing token cost**: `dcr` sits on disk and consumes nothing until invoked. A Skill adds ~50-100 tokens (description only) until activated. An MCP server would inject ~3,000-5,000 tokens of schema per turn (5 tools) on every message of every conversation — 30-50x more than a Skill.
- **CLI already complete**: 7 subcommands (sync, search, list, show, export, status, html), 114 tests, auto-sync, prefix resolution. No additional development needed for the execution layer.
- **Skill provides discovery + guidance**: The Agent Skills open specification (agentskills.io) gives the agent awareness that `dcr` exists (tier 1: ~100 tokens) and full instructions on how to use it (tier 2: loaded on activation). This bridges the gap between raw CLI (no discovery) and MCP (permanent discovery cost).
- **Occasional usage pattern**: DCR is used during self-config sessions or manual searches — not on every conversation. Paying permanent context cost for occasional use is the exact anti-pattern described by multiple sources. Skill + CLI pays only ~100 tokens when idle.
- **Local-only, single-user**: No auth, no multi-tenant, no remote API. MCP's strengths (auth, RBAC, audit, structured I/O for external systems) are irrelevant here.
- **Cross-product portability**: Agent Skills follow an open specification (agentskills.io) implemented by Windsurf, OpenAI Codex, Microsoft Agent Framework, and Anthropic Claude Code. A DCR skill would be reusable across any compatible agent. An MCP server is tied to MCP clients only.
- **Determinism and auditability**: CLI commands are reproducible, loggable, and debuggable in a terminal. MCP server debugging requires server logs.

## Alternatives Considered

- **MCP server (M7 as planned)**: Rejected. Permanent token cost (~3-5K/turn) for occasional use. 0/9 criteria favor MCP. Would require implementing `server.py`, maintaining a running process, and paying context overhead on every Cascade turn.
- **Hybrid (CLI + MCP)**: Rejected. Adds complexity without benefit. The MCP layer would duplicate the CLI's capabilities while paying the standing token cost. No use case requires structured JSON output that text/markdown doesn't cover.
- **Raw CLI (no discovery)**: Partially rejected. The CLI is the correct execution layer, but raw CLI alone lacks discovery — the agent must guess that `dcr` exists and how to use it from training data.
- **Standalone Skill + CLI**: Rejected after analysis. A generic DCR skill would be 80% documentation (command syntax, flags) and 20% procedure. The `dcr` commands are simple and self-documenting via `--help`. A skill that merely documents CLI commands is a "skill documentation" anti-pattern — it duplicates what `dcr --help` and the README already provide. The real procedural expertise (diagnostic patterns, error search strategies, conversation comparison) is context-specific and belongs in cascade-self-config, not in a generic wrapper.
- **Rule + cascade-self-config (chosen)**: A global Rule (`always_on`, ~50 tokens) provides tool discovery — "dcr exists, here's where to find it". The `dcr --help` command provides documentation on demand (0 tokens idle). The cascade-self-config skill's `references/dcr-diagnostic-patterns.md` provides the procedural expertise — how to use `dcr` for diagnostic workflows (sync, search, show, export, compare). This follows the principle: Rule = awareness, `--help` = documentation, Skill = procedure.

## Consequences

- **M7 status changes**: Deferred → Rejected. `server.py` will not be implemented.
- **`pyproject.toml`**: The `devin-conversations-retriever` entry point should be removed or marked as unused.
- **`mcp` dependency**: Can be removed from `pyproject.toml` dependencies (currently `mcp>=1.27,<2`). No code imports it.
- **Architecture doc**: `server.py` section marked as rejected with reference to this ADR.
- **Integration architecture**: Three-layer model validated against Windsurf/Devin documentation and industry best practices:
  1. **Discovery layer** — Global Rule (`always_on`, `~/.codeium/windsurf/memories/global_rules.md`): ~50 tokens permanent. Tells Cascade that `dcr` exists and where to find it.
  2. **Documentation layer** — `dcr --help` and project README: 0 tokens idle, loaded on demand. Provides command syntax, flags, and usage examples.
  3. **Procedural layer** — `cascade-self-config` skill + `references/dcr-diagnostic-patterns.md`: 0 tokens idle, loaded on skill activation. Provides diagnostic workflows (sync → search → show → analyze), error pattern search strategies, and conversation comparison procedures.
- **Files created**:
  - `~/.codeium/windsurf/memories/global_rules.md` — global Rule with `<dcr_tool_awareness>` XML tags
  - `/home/julien/Sources/cascade-self-config/references/dcr-diagnostic-patterns.md` — 6 diagnostic patterns (specific conversation, recurring errors, comparison, tool selection, wasted steps, duplicate diagnosis)
  - `cascade-self-config/SKILL.md` Phase 1 updated: `trajectory_search` → `dcr` with fallback
- **ADR-0001 amendment**: The "MCP SDK" rationale in ADR-0001 was based on the assumption that an MCP server would be built. With M7 rejected, the MCP SDK is no longer needed. ADR-0001's Python choice remains valid (for cryptography, protobuf, sqlite3) but the MCP-specific rationale is superseded by this ADR.

## Sources

| # | Source | URL | Key point |
|---|---|---|---|
| 1 | Windsurf MCP Documentation | https://docs.windsurf.com/windsurf/cascade/mcp | MCP servers load at startup, 100 tool limit |
| 2 | ContextBolt — Windsurf MCP Setup 2026 | https://contextbolt.com/blog/windsurf-mcp-setup/ | stdio servers run as persistent processes, 100 tool ceiling |
| 3 | LOW/CODE — Windsurf MCP Servers 2026 | https://www.lowcode.agency/blog/windsurf-mcp-servers | Each MCP server adds resource overhead, affects memory and startup |
| 4 | Vincent van Deth — MCP vs CLI | https://vincentvandeth.nl/blog/mcp-vs-cli-when-to-replace | 770 tokens/server/turn standing cost, CLI = 0 tokens when idle |
| 5 | AddyOsmani — MCP Deep Dive | https://addyosmani.com/agents/16-mcp-deep-dive/ | CLI 32x cheaper than MCP, 100% vs 72% reliability, decision table |
| 6 | CircleCI — MCP vs CLI | https://circleci.com/blog/mcp-vs-cli/ | CLI for inner loop (local, fast), MCP for outer loop (external, shared) |
| 7 | DEV Community — Decision Rubric | https://dev.to/bengreenberg/mcp-server-or-cli-a-decision-rubric-for-developer-tooling-2ch6 | CLI when workflow is repo-local and terminal-native |
| 8 | MindStudio — MCP vs CLI Tools | https://www.mindstudio.ai/blog/mcp-servers-vs-cli-tools-for-ai-agents | CLI for episodic/occasional use, MCP for continuous agent loops |
| 9 | Agent Skills Specification | https://agentskills.io/home | Open standard for agent skills, progressive disclosure (3 tiers) |
| 10 | agentskills.io — Specification | https://agentskills.io/specification.md | SKILL.md format, frontmatter fields, tier costs (~100 / <5K / variable tokens) |
| 11 | Microsoft Agent Framework — Adding Skills | https://learn.microsoft.com/en-us/agent-framework/journey/adding-skills | Tools = verbs (one action), Skills = expertise (domain). Context cost comparison |
| 12 | OpenAI Codex — Build Skills | https://developers.openai.com/codex/skills | Progressive disclosure, 2% context budget for skills catalog, implicit + explicit invocation |
| 13 | Windsurf Skills Documentation | https://docs.windsurf.com/windsurf/cascade/skills | Skills vs Rules vs Workflows comparison, progressive disclosure in Windsurf |
| 14 | DeepWiki — Progressive Disclosure Pattern | https://deepwiki.com/microsoft/agent-skills/5.3-progressive-disclosure-pattern | 3-tier loading (metadata → instructions → resources), token costs per tier |
| 15 | agentskills.io — Best Practices | https://agentskills.io/skill-creation/best-practices | "Add what the agent lacks, omit what it knows", "Favor procedures over declarations" |
| 16 | Perplexity — Designing Agent Skills | https://research.perplexity.ai/articles/designing-refining-and-maintaining-agent-skills-at-perplexity | "A good description says when the agent should load the Skill", routing failure modes |
| 17 | Deepsim — Designing Effective Agent Skills | https://insights.deepsim.ca/designing-effective-agent-skills/ | Single responsibility, avoid skill overlap, keep skills small |
| 18 | geta.team — Skill Composition | https://blog.geta.team/why-agent-skill-composition-is-the-new-api-design-and-most-frameworks-get-it-wrong/ | "Small verbs, not big nouns", composability, kitchen-sink anti-pattern |
| 19 | Windsurf/Devin — Memories & Rules | https://docs.devin.ai/desktop/cascade/memories | Rules activation modes (always_on, glob, model_decision, manual), best practices |
| 20 | Windsurf/Devin — Skills | https://docs.devin.ai/desktop/cascade/skills | Skills vs Rules vs Workflows, progressive disclosure, example use cases |
| 21 | Windsurf/Devin — AGENTS.md | https://docs.devin.ai/desktop/cascade/agents-md | Directory-scoped instructions, root = always-on, subdirectories = glob |

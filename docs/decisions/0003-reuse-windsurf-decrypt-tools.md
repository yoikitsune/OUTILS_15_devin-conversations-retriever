# ADR-0003: Reuse windsurf-local-user-data-decryption Tools

> Status: Accepted
> Date: 2026-07-24

## Context

The GitHub project `windsurf-local-user-data-decryption` (by D0lores/dayearleo) already contains working Python tools for:
- `decrypt_pb.py` — AES-256-GCM decryption of `.pb` files
- `scan_trajectory.py` — Protobuf wire-format parsing of CortexTrajectory
- `export_md.py` — Markdown export with round segmentation
- `find_key.py` — Key extraction from language_server binary (for future key rotations)

These tools have been tested and validated on our local `.pb` files.

## Decision

Reuse these tools as the foundation for our `decrypt.py` and `parser.py` modules, adapting them into our package structure.

## Rationale

- **Tested and working**: Validated on 50 local `.pb` files with 100% success rate
- **Well-documented**: Clear docstrings, CLI interfaces, batch modes
- **MIT licensed**: No licensing restrictions
- **Saves time**: Avoids re-implementing protobuf parsing from scratch
- **Community-maintained**: Active project with methodology documentation

## What We Reuse vs Build New

| Module | Source | Action |
|---|---|---|
| `decrypt.py` | `decrypt_pb.py` | Adapt: extract `decrypt_one()` function, remove CLI |
| `parser.py` | `scan_trajectory.py` | Adapt: extract `parse_trajectory()`, `parse_step()`, `iter_fields()` |
| `indexer.py` | New | Build: SQLite FTS5 indexing |
| `search.py` | New | Build: FTS5 query engine |
| `server.py` | New | Build: FastMCP server with tools |
| `models.py` | New | Build: Pydantic models |

## Consequences

- Must attribute the original project in README
- Must track upstream changes (key rotation, protobuf schema changes)
- `find_key.py` kept as reference but not integrated (key is currently stable)

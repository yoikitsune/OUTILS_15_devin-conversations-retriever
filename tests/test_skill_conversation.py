"""Tests for the @conversation skill (Phase 4).

Validates that the skill documentation exists, has the correct frontmatter
format, and references the right dcr commands. These are documentation
consistency tests — they ensure the skill stays in sync with the CLI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_PATH = Path(__file__).resolve().parent.parent / ".devin/skills/dcr-conversation/SKILL.md"


# --- Skill file existence ---


def test_skill_file_exists():
    """The @conversation skill SKILL.md file exists."""
    assert SKILL_PATH.exists(), f"Skill file not found at {SKILL_PATH}"


def test_skill_file_not_empty():
    """The skill file is not empty."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert len(content) > 100, "Skill file is too short"


# --- Frontmatter ---


def test_skill_has_frontmatter():
    """The skill file has YAML frontmatter with name and description."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert content.startswith("---"), "Skill file must start with YAML frontmatter"

    # Extract frontmatter
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Frontmatter not properly closed"
    frontmatter = parts[1]

    assert "name:" in frontmatter, "Frontmatter must have 'name'"
    assert "description:" in frontmatter, "Frontmatter must have 'description'"


def test_skill_name_is_dcr_conversation():
    """The skill name is 'dcr-conversation'."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)", content, re.MULTILINE)
    assert match, "No 'name' field in frontmatter"
    assert match.group(1) == "dcr-conversation", f"Expected 'dcr-conversation', got '{match.group(1)}'"


def test_skill_description_mentions_keywords():
    """The skill description mentions key trigger words."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    # Extract description from frontmatter
    match = re.search(r"^description:\s*(.+?)(?:\n---|\n\n)", content, re.MULTILINE | re.DOTALL)
    if match:
        desc = match.group(1).lower()
        assert "conversation" in desc, "Description should mention 'conversation'"
        assert "dcr" in desc or "archive" in desc, "Description should mention dcr or archive"


# --- Content consistency ---


def test_skill_references_dcr_commands():
    """The skill references the key dcr commands."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    required_commands = ["dcr search", "dcr show", "dcr export", "dcr list"]
    for cmd in required_commands:
        assert cmd in content, f"Skill should reference '{cmd}'"


def test_skill_mentions_source_type_filter():
    """The skill mentions --source-type filter (Phase 2 feature)."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "--source-type" in content, "Skill should mention --source-type filter"


def test_skill_mentions_full_tree():
    """The skill mentions --full-tree flag (Phase 2 feature)."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "--full-tree" in content, "Skill should mention --full-tree flag"


def test_skill_mentions_no_sync():
    """The skill explains the --no-sync trade-off (sync is fast, prefer freshness)."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "--no-sync" in content, "Skill should mention --no-sync flag"
    assert "fraîcheur" in content.lower() or "fraicheur" in content.lower(), (
        "Skill should explain that sync is fast and freshness matters more than --no-sync"
    )


def test_skill_has_procedure_section():
    """The skill has a procedure section."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "Procédure" in content or "Procedure" in content, "Skill should have a procedure section"


def test_skill_has_examples():
    """The skill has usage examples."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "Exemple" in content or "Example" in content, "Skill should have examples"


def test_skill_warns_about_id_confusion():
    """The skill warns about the dcr ID vs trajectory_search UUID confusion."""
    if not SKILL_PATH.exists():
        pytest.skip("Skill file not found")
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "trajectory_search" in content, "Skill should warn about trajectory_search ID confusion"

"""The bench team in .claude/agents/ can't reach an Epiphan Edge write tool or skip permissions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "agents"
AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))

# The write tools listed under permissions.ask in .claude/settings.json, by suffix so both server names match.
EDGE_WRITE_TOOLS = (
    "batch_recording",
    "start_stream_endpoint",
    "stop_stream_endpoint",
    "create_cms_event",
    "update_cms_event",
    "delete_cms_event",
    "cms_event_action",
    "confirm_cms_event_on_device",
    "create_stream_endpoint",
    "update_stream_endpoint",
    "delete_stream_endpoint",
    "apply_team_preset",
    "switch_device_to_cms",
    "batch_reboot",
    "batch_firmware_update",
)


def frontmatter(path: Path) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    assert match, f"{path.name} has no frontmatter"
    return match.group(1)


def tools_of(block: str) -> list[str]:
    return re.findall(r"^\s*-\s*(\S+)\s*$", block, re.M)


def test_the_team_exists() -> None:
    assert AGENT_FILES, "no agent definitions in .claude/agents/"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_name_matches_filename(path: Path) -> None:
    assert re.search(rf"^name: {re.escape(path.stem)}$", frontmatter(path), re.M)


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_tools_are_listed_one_by_one(path: Path) -> None:
    tools = tools_of(frontmatter(path))
    assert tools, f"{path.name} lists no tools"
    for tool in tools:
        if tool.startswith("mcp__"):
            assert "*" not in tool, f"{path.name} grants a wildcard MCP tool: {tool}"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_no_edge_write_tools(path: Path) -> None:
    for tool in tools_of(frontmatter(path)):
        assert not tool.endswith(EDGE_WRITE_TOOLS), f"{path.name} lists an Edge write tool: {tool}"


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_no_bypass_mode(path: Path) -> None:
    block = frontmatter(path)
    assert "dontAsk" not in block and "bypassPermissions" not in block, f"{path.name} skips permission prompts"

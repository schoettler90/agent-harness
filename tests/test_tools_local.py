import json
from pathlib import Path

import pytest
from agents.run_config import RunConfig
from agents.tool_context import ToolContext

from harness.tools import resolve_tools


def _ctx(name: str) -> ToolContext:
    return ToolContext(
        context=None,
        tool_name=name,
        tool_call_id="test-call",
        tool_arguments="{}",
        run_config=RunConfig(tracing_disabled=True),
    )


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AGENT_WORKDIR", str(tmp_path))
    # Reload settings module so the new env var is picked up.
    import importlib

    import src.settings as settings_mod

    importlib.reload(settings_mod)
    # Reload tools package first (clears TOOL_REGISTRY), then per-tool modules
    # so each re-registers against the fresh registry and rebinds settings.
    for mod in [
        "harness.tools",
        "harness.tools.shell",
        "harness.tools.filesystem",
        "harness.tools.memory",
        "harness.tools.skills",
    ]:
        if mod in importlib.sys.modules:
            importlib.reload(importlib.sys.modules[mod])
    return tmp_path


async def _invoke(tool, **kwargs) -> str:
    """Invoke a FunctionTool with raw kwargs, bypassing the agent loop."""
    return await tool.on_invoke_tool(_ctx(tool.name), json.dumps(kwargs))


@pytest.mark.asyncio
async def test_shell_tool_runs_command(workdir: Path):
    tools, _ = resolve_tools(["shell"])
    [shell] = tools
    out = await _invoke(shell, command="echo hello")
    assert "hello" in out
    assert "exit_code: 0" in out


@pytest.mark.asyncio
async def test_filesystem_write_read_list(workdir: Path):
    tools, _ = resolve_tools(["filesystem"])
    by_name = {t.name: t for t in tools}

    write_result = await _invoke(by_name["write_file"], path="hello.txt", content="hi there")
    assert "Wrote" in write_result
    assert (workdir / "hello.txt").read_text() == "hi there"

    read_result = await _invoke(by_name["read_file"], path="hello.txt")
    assert "hi there" in read_result
    assert read_result.startswith("1\t")

    listing = await _invoke(by_name["list_dir"], path=".")
    assert "hello.txt" in listing


@pytest.mark.asyncio
async def test_filesystem_rejects_escape(workdir: Path):
    tools, _ = resolve_tools(["filesystem"])
    by_name = {t.name: t for t in tools}
    out = await _invoke(by_name["read_file"], path="../etc/passwd")
    assert out.startswith("Error")


@pytest.mark.asyncio
async def test_memory_save_load(workdir: Path):
    tools, _ = resolve_tools(["memory"])
    by_name = {t.name: t for t in tools}

    saved = await _invoke(by_name["memory_save"], key="foo", value="bar")
    assert "foo" in saved

    loaded = await _invoke(by_name["memory_load"], key="foo")
    assert loaded == "bar"

    missing = await _invoke(by_name["memory_load"], key="nope")
    assert "no value" in missing


@pytest.mark.asyncio
async def test_skills_list_and_load(tmp_path: Path):
    skills_root = tmp_path / "skills"
    (skills_root / "alpha").mkdir(parents=True)
    (skills_root / "alpha" / "SKILL.md").write_text("# alpha skill\nDoes the thing.")

    from harness.tools.skills import make_skills_tools

    tools = make_skills_tools(skills_dir=skills_root)
    by_name = {t.name: t for t in tools}

    listing = await _invoke(by_name["list_skills"])
    assert "alpha" in listing

    body = await _invoke(by_name["load_skill"], name="alpha")
    assert "alpha skill" in body

    missing = await _invoke(by_name["load_skill"], name="missing")
    assert missing.startswith("Error")


def test_mcp_loader_missing_file_returns_empty(tmp_path: Path):
    from harness.tools.mcp import load_mcp_servers_from_config

    assert load_mcp_servers_from_config(tmp_path / "nope.json") == []


def test_mcp_loader_parses_config(tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {"command": "echo", "args": ["hi"]},
                    "remote": {"url": "https://example.com/mcp"},
                    "broken": {},
                }
            }
        )
    )
    from harness.tools.mcp import load_mcp_servers_from_config

    servers = load_mcp_servers_from_config(cfg)
    assert len(servers) == 2

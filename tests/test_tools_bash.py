import platform
from unittest.mock import MagicMock

import pytest

from harness.tools.bash import make_bash_tool


def _make_ctx(tool_name: str = "bash"):
    ctx = MagicMock()
    ctx.tool_name = tool_name
    return ctx


def test_make_bash_tool_returns_function_tool(tmp_sandbox):
    tool = make_bash_tool(sandbox_dir=tmp_sandbox)
    assert tool.name == "bash"


@pytest.mark.asyncio
async def test_bash_executes_command(tmp_sandbox):
    tool = make_bash_tool(sandbox_dir=tmp_sandbox)
    ctx = _make_ctx()
    if platform.system() == "Windows":
        result = await tool.on_invoke_tool(ctx, '{"command": "dir"}')
    else:
        result = await tool.on_invoke_tool(ctx, '{"command": "ls"}')
    assert "exit_code=0" in result
    assert "test.txt" in result

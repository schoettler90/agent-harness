from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harness.tools.file_search import make_file_search_tool


def _make_ctx(tool_name: str = "file_search"):
    ctx = MagicMock()
    ctx.tool_name = tool_name
    return ctx


def test_make_file_search_tool_returns_function_tool(tmp_sandbox):
    tool = make_file_search_tool(sandbox_dir=tmp_sandbox)
    assert tool.name == "file_search"


@pytest.mark.asyncio
async def test_file_search_finds_content(tmp_sandbox):
    tool = make_file_search_tool(sandbox_dir=tmp_sandbox)
    ctx = _make_ctx()
    result = await tool.on_invoke_tool(ctx, '{"query": "hello"}')
    assert "test.txt" in result

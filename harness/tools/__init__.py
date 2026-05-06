from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents import Tool

TOOL_REGISTRY: dict[str, Callable[..., Tool | list[Tool]]] = {}


def register_tool(name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = func
        return func
    return decorator


def _ensure_registered() -> None:
    if TOOL_REGISTRY:
        return
    import harness.tools.bash  # noqa: F401
    import harness.tools.file_search  # noqa: F401
    import harness.tools.web_search  # noqa: F401
    from harness.tools.skills import make_skill_tools

    TOOL_REGISTRY["skills"] = make_skill_tools


def resolve_tools(names: list[str], **kwargs: Any) -> list[Tool]:
    _ensure_registered()
    tools: list[Tool] = []
    for name in names:
        if name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {name!r}. Available: {list(TOOL_REGISTRY.keys())}")
        result = TOOL_REGISTRY[name](**kwargs)
        if isinstance(result, list):
            tools.extend(result)
        else:
            tools.append(result)
    return tools

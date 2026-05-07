from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents import Tool
from agents.mcp import MCPServer

TOOL_REGISTRY: dict[str, Callable[..., Tool | list[Tool]]] = {}


def register_tool(name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = func
        return func

    return decorator


_REGISTERED = False


def _ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    import harness.tools.filesystem  # noqa: F401
    import harness.tools.memory  # noqa: F401
    import harness.tools.shell  # noqa: F401
    import harness.tools.skills  # noqa: F401
    import harness.tools.web_search  # noqa: F401  (registers web_search and web_fetch)
    _REGISTERED = True


def resolve_tools(
    names: list[str],
    mcp_config_path: Path | None = None,
    **kwargs: Any,
) -> tuple[list[Tool], list[MCPServer]]:
    """Resolve requested tool names into function tools and MCP servers.

    `names` lists function-tool registry keys (shell, filesystem, memory, skills,
    web_search). MCP servers are loaded separately from `mcp_config_path` (or
    skipped if the file is absent).
    """
    _ensure_registered()
    tools: list[Tool] = []
    for name in names:
        if name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {name!r}. Available: {sorted(TOOL_REGISTRY.keys())}")
        result = TOOL_REGISTRY[name](**kwargs)
        if isinstance(result, list):
            tools.extend(result)
        else:
            tools.append(result)

    mcp_servers: list[MCPServer] = []
    if mcp_config_path is not None:
        from harness.tools.mcp import load_mcp_servers_from_config

        mcp_servers = load_mcp_servers_from_config(mcp_config_path)

    return tools, mcp_servers

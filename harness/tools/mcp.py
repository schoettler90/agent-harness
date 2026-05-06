from __future__ import annotations

from agents.mcp import MCPServerStdio, MCPServerStreamableHttp
from pydantic import Field
from pydantic.dataclasses import dataclass


@dataclass
class MCPStdioConfig:
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None


@dataclass
class MCPHttpConfig:
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


def make_local_mcp(config: MCPStdioConfig) -> MCPServerStdio:
    params = {
        "command": config.command,
        "args": config.args,
        "env": config.env,
    }
    if config.cwd:
        params["cwd"] = config.cwd
    return MCPServerStdio(params=params, cache_tools_list=True)


def make_remote_mcp(config: MCPHttpConfig) -> MCPServerStreamableHttp:
    params = {
        "url": config.url,
        "headers": config.headers,
    }
    return MCPServerStreamableHttp(params=params, cache_tools_list=True)

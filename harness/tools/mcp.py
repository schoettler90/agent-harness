import json
from pathlib import Path

from agents.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHttp
from pydantic import Field
from pydantic.dataclasses import dataclass

from src.utils import LoggerSetup

logger = LoggerSetup("MCPLoader")


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


def load_mcp_servers_from_config(path: Path) -> list[MCPServer]:
    """Load MCP servers from a JSON config file.

    Schema (Claude Desktop style):
        {
          "mcpServers": {
            "name": {"command": "...", "args": [...], "env": {...}, "cwd": "..."},
            "name2": {"url": "...", "headers": {...}}
          }
        }

    If the file does not exist, returns an empty list.
    """
    path = Path(path)
    if not path.exists():
        logger.info("MCP config not found at {p}, no MCP servers will be loaded", p=str(path))
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to parse MCP config {p}: {e}", p=str(path), e=e)
        return []

    entries = raw.get("mcpServers", {})
    servers: list[MCPServer] = []
    for name, entry in entries.items():
        try:
            if "command" in entry:
                servers.append(
                    make_local_mcp(
                        MCPStdioConfig(
                            command=entry["command"],
                            args=entry.get("args", []),
                            env=entry.get("env", {}),
                            cwd=entry.get("cwd"),
                        )
                    )
                )
            elif "url" in entry:
                servers.append(
                    make_remote_mcp(
                        MCPHttpConfig(
                            url=entry["url"],
                            headers=entry.get("headers", {}),
                        )
                    )
                )
            else:
                logger.warning("MCP entry {n} has neither command nor url, skipping", n=name)
        except Exception as e:
            logger.error("Failed to build MCP server {n}: {e}", n=name, e=e)

    logger.info("Loaded {n} MCP server(s) from {p}", n=len(servers), p=str(path))
    return servers

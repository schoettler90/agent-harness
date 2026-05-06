# CLAUDE.md — agent-harness

## Project Overview

`agent-harness` is a FastAPI backend that wraps an OpenAI Agents SDK-style agent loop with a provider-agnostic model layer (LiteLLM). It streams normalized events over SSE to a frontend and exposes a pluggable tool surface (web search, file search, bash, MCP, skills).

## Always Use `uv`

Never use bare `python`, `pip`, or `pip install`. Always use `uv`.

```bash
uv run uvicorn harness.main:app --reload   # run
uv run pytest                              # test
uv run ruff check .                        # lint
uv add <package>                           # add dependency
uv sync                                    # sync env
```

Python version is **3.14** — pinned in `.python-version` and `pyproject.toml`.

## Running Locally

```bash
cp .env.example .env
uv sync
uv run uvicorn harness.main:app --reload --port 8000
```

## Testing

```bash
uv run pytest
uv run pytest tests/test_stream.py   # single module
```

## Module Structure

```
agent-harness/
├── harness/
│   ├── main.py             # FastAPI app, /run SSE endpoint, /health
│   ├── agent.py            # Agent loop (openai-agents + LiteLLM)
│   ├── stream.py           # HarnessEvent envelope + SSE formatter
│   ├── litellm_factory.py  # Provider-agnostic LiteLLM client
│   ├── tools/
│   │   ├── web_search.py
│   │   ├── file_search.py
│   │   ├── bash.py
│   │   ├── mcp.py
│   │   └── skills.py
│   └── filesystem/
│       ├── local.py
│       ├── s3.py
│       └── google_drive.py
├── src/
│   ├── utils.py            # LoggerSetup (loguru)
│   └── settings.py         # Pydantic-dataclass Settings
├── skills/                 # SKILL.md manifests + scripts
├── tests/
├── pyproject.toml
├── .python-version         # 3.14
└── .env.example
```

## Git Commits — Conventional Commits

```
<type>: <short description>
```

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only changes |
| `chore` | Maintenance, deps, tooling, config |
| `refactor` | Code restructure with no behavior change |
| `test` | Adding or updating tests |
| `style` | Formatting, whitespace (no logic change) |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |

## Logging — Loguru

All logging must use **loguru** via `LoggerSetup` — never stdlib `logging` or `print()`.

```python
from src.utils import LoggerSetup
logger = LoggerSetup("ModuleName")

logger.info("started")
logger.success("done")
logger.warning("retrying")
logger.error("failed: {e}", e=err)
```

## Data Modeling — Pydantic Dataclasses

All inter-layer data (requests, tool configs, stream events, filesystem configs) must use `pydantic.dataclasses.dataclass` — never plain `dict`, plain `@dataclass`, or `BaseModel`.

```python
from pydantic.dataclasses import dataclass

@dataclass
class RunRequest:
    prompt: str
    model: str
    tools: list[str]
```

## Streaming Event Envelope

Every SSE event must be a `HarnessEvent` — no raw output crosses module boundaries.

```python
@dataclass
class HarnessEvent:
    event: str       # tool_called | tool_output | message_delta | message_done | error | done
    tool: str | None # web_search | file_search | bash | mcp | skill | None
    data: dict
    timestamp: str   # ISO-8601
```

## Tool Interface Contract

Each tool module exposes one factory function with a typed Pydantic dataclass config:

```python
def make_tool(config: <ToolConfig>) -> FunctionTool | HostedMCPTool | MCPServer:
    ...
```

## FastAPI Conventions

- `POST /run` — body: `AgentRunRequest`, response: `text/event-stream`
- `GET /health` — returns `{"status": "ok"}`
- All handlers are `async def`
- Use `StreamingResponse` with an async generator for SSE

## Model Provider

Set `MODEL` env var — LiteLLM routes to the correct provider automatically.

```
MODEL=gpt-4o
MODEL=claude-opus-4-7
MODEL=gemini/gemini-2.5-pro
MODEL=ollama/llama3
```

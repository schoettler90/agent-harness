# CLAUDE.md — agent-harness

## Project Overview

`agent-harness` is a FastAPI backend that wraps an OpenAI Agents SDK-style agent loop with a provider-agnostic model layer (LiteLLM). It streams normalized events over SSE to a frontend and exposes a pluggable tool surface (web search, file search, bash, MCP, skills).

## Critical: Always Use `uv`

- **Never** use bare `python`, `pip`, or `pip install`.
- **Always** run code with `uv run <command>` (e.g. `uv run uvicorn harness.main:app`).
- **Always** add dependencies with `uv add <package>`.
- **Always** sync the environment with `uv sync`.
- Python version is **3.14** — set in `.python-version` and `pyproject.toml`.

```bash
# Correct
uv run python script.py
uv run uvicorn harness.main:app --reload
uv add fastapi litellm openai-agents

# Wrong — never do this
python script.py
pip install fastapi
```

## Module Structure (evolving)

```
agent-harness/
├── harness/
│   ├── main.py          # FastAPI app, /run SSE endpoint
│   ├── agent.py         # Agent loop using openai-agents + LiteLLM
│   ├── stream.py        # Normalized streaming event envelope
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
├── skills/              # SKILL.md manifests + scripts
├── pyproject.toml
├── .python-version      # 3.14
└── .env.example
```

## Git Commits — Conventional Commits

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```
<type>: <short description>
```

Allowed types:

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

Examples:
```
feat: add web search tool with SSE streaming
fix: handle empty tool output in HarnessEvent
docs: update README with filesystem sources
chore: add ruff to dev dependencies
refactor: extract stream envelope into harness/stream.py
test: add unit tests for LiteLLMFactory.resolve_model
```

## Logging — Loguru

All logging must use **loguru** — never the stdlib `logging` module, `print()`, or any other logger.

```python
# Correct
from loguru import logger

logger.info("Agent loop started")
logger.success("Run complete")
logger.warning("Retrying tool call")
logger.error("Tool failed: {error}", error=e)

# Wrong — never use these
import logging
print("debug info")
logging.getLogger(__name__).info(...)
```

Each module gets its own named sink via the shared `LoggerSetup` utility in `src/utils.py`:

```python
from src.utils import LoggerSetup
logger = LoggerSetup("ModuleName")
```

## Data Modeling — Pydantic Dataclasses

All data passed between layers (request bodies, tool inputs/outputs, stream events, filesystem configs) must be typed using **Pydantic dataclasses** — not plain `dict`, plain `@dataclass`, or `BaseModel`.

```python
# Correct
from pydantic.dataclasses import dataclass

@dataclass
class RunRequest:
    prompt: str
    model: str
    tools: list[str]

# Wrong — never use these for inter-layer data
from dataclasses import dataclass  # plain dataclass, no validation
class RunRequest(BaseModel): ...   # BaseModel is fine for DB/API schemas but not preferred here
def run(data: dict): ...           # untyped dict
```

Use `pydantic.dataclasses.dataclass` everywhere so that field validation, serialization (`.model_dump()`, `.model_dump_json()`), and JSON schema generation are all available automatically.

## Streaming Event Envelope

Every event pushed over SSE must conform to this schema. No tool is allowed to emit raw output — all output goes through the envelope.

```python
from pydantic.dataclasses import dataclass

@dataclass
class HarnessEvent:
    event: str       # "tool_called" | "tool_output" | "message_delta" | "message_done" | "error" | "done"
    tool: str | None # "web_search" | "file_search" | "bash" | "mcp" | "skill" | None
    data: dict       # tool-specific payload
    timestamp: str   # ISO-8601
```

SSE format:
```
event: tool_called
data: {"tool": "web_search", "query": "...", "timestamp": "..."}

event: tool_output
data: {"tool": "web_search", "result": [...], "timestamp": "..."}
```

## Tool Interface Contract

Each tool module must expose a single factory function. Tool config is always a typed Pydantic dataclass — never a raw `dict`.

```python
from pydantic.dataclasses import dataclass

@dataclass
class WebSearchConfig:
    max_results: int = 5
    provider: str = "openai"

def make_tool(config: WebSearchConfig) -> FunctionTool | HostedMCPTool | MCPServer:
    ...
```

Tools are registered in `harness/agent.py` and receive their config dataclass from the run request.

## FastAPI Conventions

- All agent runs go through `POST /run` — body: `{prompt, model, tools, filesystem}`.
- Response is `text/event-stream` (SSE).
- `GET /health` returns `{"status": "ok"}`.
- No sync route handlers — everything is `async def`.
- Use `fastapi.responses.StreamingResponse` with an async generator for SSE.

## Model Provider (LiteLLM)

The `MODEL` env var selects the model. LiteLLM translates this to the correct provider SDK. Examples:

```
MODEL=gpt-4o              # OpenAI
MODEL=claude-opus-4-7     # Anthropic
MODEL=gemini/gemini-2.5-pro  # Google
MODEL=ollama/llama3        # Local via Ollama
```

Pass `model=os.environ["MODEL"]` to the LiteLLM completion call or the openai-agents LiteLLM adapter.

## Filesystem

The sandbox filesystem is loaded before the agent loop starts. The source is selected by the `filesystem` field in the run request:

- `{"source": "local", "path": "/abs/path"}` — symlink or copy into sandbox dir
- `{"source": "s3", "bucket": "...", "prefix": "..."}` — download via boto3
- `{"source": "google_drive", "folder_id": "..."}` — download via Google Drive API

## Skills

Skills live in `skills/<name>/`. Each skill has:
- `SKILL.md` — manifest: name, description, trigger phrase, steps
- `scripts/` — shell scripts or Python helpers
- `references/` — static reference files

Skills are loaded lazily (only injected into context when invoked) to avoid bloating the system prompt.

## Testing

```bash
uv run pytest
# or for a single module
uv run pytest harness/tests/test_stream.py
```

## Running Locally

```bash
cp .env.example .env
# fill in API keys in .env
uv sync
uv run uvicorn harness.main:app --reload --port 8000
```

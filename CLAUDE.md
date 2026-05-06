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

## Streaming Event Envelope

Every event pushed over SSE must conform to this schema. No tool is allowed to emit raw output — all output goes through the envelope.

```python
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

Each tool module must expose a single factory function:

```python
def make_tool(config: dict) -> FunctionTool | HostedMCPTool | MCPServer:
    ...
```

Tools are registered in `harness/agent.py` and receive `config` from the run request.

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

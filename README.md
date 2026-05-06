# agent-harness

A modular, provider-agnostic agent harness built on the OpenAI Agents SDK pattern. Exposes a FastAPI backend that runs an agent loop, streams standardized events to the frontend, and integrates a pluggable tool surface via MCP, bash, file search, web search, and skills.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLIENT / UI                      │
│              (SSE stream consumer)                  │
└──────────────────────┬──────────────────────────────┘
                       │  POST /run  →  SSE stream
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                     │
│  ┌──────────────────────────────────────────────┐   │
│  │               HARNESS                        │   │
│  │  ┌──────────────┐   ┌────────────────────┐  │   │
│  │  │  AGENT LOOP  │   │    MCP / TOOLS     │  │   │
│  │  │  (LiteLLM)   │◄──│  Web Search        │  │   │
│  │  │              │   │  File Search       │  │   │
│  │  │  stream_     │   │  Bash / Shell      │  │   │
│  │  │  events()    │   │  MCP Servers       │  │   │
│  │  │              │   │  Skills            │  │   │
│  │  └──────────────┘   └────────────────────┘  │   │
│  └──────────────────────────────────────────────┘   │
│                       │                             │
│  ┌────────────────────▼────────────────────────┐   │
│  │              FILESYSTEM                      │   │
│  │   Local dir  │  Amazon S3  │  Google Drive  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Tools

| Tool | Description |
|------|-------------|
| **Web Search** | Live internet search via configured provider |
| **File Search** | Semantic search over the mounted filesystem |
| **MCP** | Local (`stdio`) and remote (`streamable-http`) MCP servers |
| **Bash / Code Interpreter** | Shell command execution inside the sandbox |
| **Skills** | `SKILL.md`-based reusable workflow packages |
| **Remote MCP** | Hosted MCP endpoints (HostedMCPTool pattern) |

## Data Modeling

All inter-layer data (requests, tool configs, stream events) is typed with **Pydantic dataclasses** (`pydantic.dataclasses.dataclass`). This gives automatic field validation, `.model_dump_json()` serialization, and JSON schema generation without switching between `BaseModel` and plain dataclasses.

## Streaming Event Envelope

Every tool call and agent event is normalized into a single Pydantic dataclass before being pushed over SSE — no raw dicts cross module boundaries:

```python
from pydantic.dataclasses import dataclass

@dataclass
class HarnessEvent:
    event: str       # tool_called | tool_output | message_delta | message_done | error | done
    tool: str | None # web_search | file_search | bash | mcp | skill | None
    data: dict       # tool-specific payload
    timestamp: str   # ISO-8601
```

Wire format (SSE):
```
event: tool_called
data: {"tool": "web_search", "query": "...", "timestamp": "2026-05-07T00:00:00Z"}

event: tool_output
data: {"tool": "web_search", "result": [...], "timestamp": "2026-05-07T00:00:00Z"}
```

## Filesystem Sources

The agent sandbox filesystem can be loaded from:

- **Local directory** — the directory the agent is invoked from
- **Amazon S3** — mounted via s3fs / boto3
- **Google Drive** — mounted via PyDrive2 / Google API

## Quickstart

```bash
# Install dependencies
uv sync

# Run the FastAPI backend
uv run uvicorn harness.main:app --reload --port 8000

# Run with a specific model provider (LiteLLM)
MODEL=gpt-4o uv run uvicorn harness.main:app --reload
MODEL=claude-opus-4-7 uv run uvicorn harness.main:app --reload
MODEL=gemini/gemini-2.5-pro uv run uvicorn harness.main:app --reload
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MODEL` | LiteLLM model string (e.g. `gpt-4o`, `claude-opus-4-7`) |
| `OPENAI_API_KEY` | OpenAI key (if using OpenAI models) |
| `ANTHROPIC_API_KEY` | Anthropic key (if using Claude models) |
| `GOOGLE_API_KEY` | Google key (if using Gemini models) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 filesystem source |
| `GOOGLE_DRIVE_CREDENTIALS` | Path to Google Drive service account JSON |
| `MCP_SERVER_URL` | Remote MCP server endpoint |

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK — Next Evolution](https://openai.com/index/the-next-evolution-of-the-agents-sdk/)
- [LiteLLM](https://docs.litellm.ai/)
- [MCP Specification](https://modelcontextprotocol.io/)

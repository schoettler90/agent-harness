# agent-harness

A modular, provider-agnostic agent harness built on the OpenAI Agents SDK pattern. Exposes a FastAPI backend that runs an agent loop, streams normalized events to the frontend, and integrates a pluggable tool surface over a sandbox filesystem.

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
| **File Search** | Search over the mounted sandbox filesystem |
| **Bash** | Shell command execution inside the sandbox |
| **MCP** | Local (`stdio`) and remote (`streamable-http`) MCP servers |
| **Skills** | `SKILL.md`-based reusable workflow packages |

## Filesystem Sources

| Source | Description |
|--------|-------------|
| `local` | Directory the agent is invoked from |
| `s3` | Amazon S3 bucket prefix (via boto3) |
| `google_drive` | Google Drive folder (via Google API) |

## Quickstart

```bash
cp .env.example .env   # add API keys
uv sync
uv run uvicorn harness.main:app --reload --port 8000
```

## Running with a specific model

```bash
MODEL=gpt-4o uv run uvicorn harness.main:app --reload
MODEL=claude-opus-4-7 uv run uvicorn harness.main:app --reload
MODEL=gemini/gemini-2.5-pro uv run uvicorn harness.main:app --reload
```

## Testing

```bash
uv run pytest
uv run pytest tests/test_stream.py   # single module
```

## Linting

```bash
uv run ruff check .
uv run ruff format .
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MODEL` | LiteLLM model string (e.g. `gpt-4o`, `claude-opus-4-7`) |
| `OPENAI_API_KEY` | OpenAI key |
| `ANTHROPIC_API_KEY` | Anthropic key |
| `GOOGLE_API_KEY` | Google / Gemini key |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 filesystem source |
| `GOOGLE_DRIVE_CREDENTIALS` | Path to Google Drive service account JSON |
| `MCP_SERVER_URL` | Remote MCP server endpoint |

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [LiteLLM](https://docs.litellm.ai/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Implementation plan](PLAN.md)

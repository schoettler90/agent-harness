# Implementation Plan — agent-harness

## Goal

Build a provider-agnostic agent harness that exposes a FastAPI `/run` SSE endpoint, runs an OpenAI Agents SDK-style agent loop driven by LiteLLM, and streams normalized events from a pluggable tool surface (web search, file search, bash, MCP, skills) operating over a sandbox filesystem (local / S3 / Google Drive).

This plan is broken into **8 phases**. Each phase is independently testable end-to-end. Do not start phase N+1 until phase N is verified.

---

## Phase 0 — Foundation (utilities)

**Why first:** `harness/litellm_factory.py` already imports `from src.utils import LoggerSetup`, but `src/` doesn't exist. Nothing else can run until this is fixed.

### Files
- `src/__init__.py`
- `src/utils.py` — `LoggerSetup(name: str) -> loguru.Logger` with module-named sink and ISO timestamp format
- `src/settings.py` — Pydantic-dataclass `Settings` loaded from `.env` (model, API keys, sandbox dir)
- `.env.example` — template with all keys from README

### Verification
- `uv run python -c "from src.utils import LoggerSetup; LoggerSetup('test').info('ok')"` prints a formatted log line
- `uv run python harness/litellm_factory.py` runs `stream_main()` end-to-end (requires `OPENAI_API_KEY` or `GOOGLE_API_KEY`)

---

## Phase 1 — Stream Envelope

**Why:** Every downstream component (agent loop, tools, FastAPI endpoint) emits or consumes `HarnessEvent`. Define it before anything else uses it.

### Files
- `harness/stream.py`
  - `HarnessEvent` Pydantic dataclass — `event`, `tool`, `data`, `timestamp` (matches CLAUDE.md schema)
  - `EventType` `Literal` — `tool_called | tool_output | message_delta | message_done | error | done`
  - `ToolName` `Literal` — `web_search | file_search | bash | mcp | skill | None`
  - `to_sse(event: HarnessEvent) -> str` — formats as `event: <type>\ndata: <json>\n\n`
  - `from_agent_event(raw)` — adapter from `openai-agents` `RunItemStreamEvent` / `RawResponsesStreamEvent` → `HarnessEvent`

### Verification
- `uv run pytest tests/test_stream.py` — round-trip event → SSE → parsed back
- Snapshot test: feed a fake `tool_called` event → assert exact SSE wire format

---

## Phase 2 — Minimal Agent Loop

**Why:** Get a working agent that streams plain-text responses through `HarnessEvent` envelopes — no tools yet. Proves the LiteLLM ↔ openai-agents ↔ stream wiring.

### Files
- `harness/agent.py`
  - `AgentRunRequest` Pydantic dataclass — `prompt`, `model`, `tools: list[str]`, `filesystem: FilesystemConfig | None`
  - `build_agent(req: AgentRunRequest) -> Agent` — uses `LiteLLMFactory.resolve_model()` + `openai-agents` `Agent` with no tools
  - `run_streamed(req: AgentRunRequest) -> AsyncIterator[HarnessEvent]` — wraps `Runner.run_streamed()`, converts each event via `from_agent_event()`

### Verification
- `uv run python -m harness.agent "Hello, who are you?"` — streams tokens to stdout as `HarnessEvent`s

---

## Phase 3 — FastAPI App + SSE Endpoint

**Why:** Real HTTP surface so a frontend can consume the stream. Keep it minimal; add tools in later phases.

### Files
- `harness/main.py`
  - `app = FastAPI()`
  - `GET /health` → `{"status": "ok"}`
  - `POST /run` body: `AgentRunRequest`, response: `StreamingResponse(media_type="text/event-stream")` driven by `run_streamed()` + `to_sse()`
  - CORS middleware (allow all in dev)

### Verification
- `uv run uvicorn harness.main:app --reload`
- `curl -N -X POST localhost:8000/run -H "content-type: application/json" -d '{"prompt":"hello","model":"gemini-2.5-flash","tools":[]}'` — receives SSE stream

---

## Phase 4 — Tools (one per sub-phase)

Each tool: implement, register, add an integration test, commit. Order is by complexity.

### 4a — Bash / Shell tool
- `harness/tools/bash.py` — wraps `openai-agents` `ShellTool` in **local mode** rooted at `Settings.sandbox_dir`
- `BashConfig` Pydantic dataclass — `cwd`, `timeout`, `network: bool = False`
- Emits `tool_called` (with command) + `tool_output` (with stdout/stderr/exit_code) `HarnessEvent`s

### 4b — File Search tool
- `harness/tools/file_search.py` — `@function_tool` over the mounted sandbox filesystem
- Backend: ripgrep via subprocess for speed; fall back to Python `pathlib.glob` if rg unavailable
- `FileSearchConfig` — `pattern`, `max_results`, `glob_filter`

### 4c — Web Search tool
- `harness/tools/web_search.py` — start with hosted `WebSearchTool` from openai-agents (OpenAI provider only)
- `WebSearchConfig` — `max_results`, `provider: Literal["openai", "tavily"] = "openai"`
- Tavily fallback for non-OpenAI models (gated by `TAVILY_API_KEY`)

### 4d — MCP (local + remote)
- `harness/tools/mcp.py`
  - `make_local_mcp(config: MCPStdioConfig) -> MCPServerStdio`
  - `make_remote_mcp(config: MCPHttpConfig) -> HostedMCPTool` (OpenAI) or `MCPServerStreamableHttp` (other providers)
- `MCPStdioConfig` — `command`, `args`, `env`
- `MCPHttpConfig` — `url`, `headers`, `require_approval: bool`

### 4e — Skills
- `harness/tools/skills.py`
  - Discover `skills/<name>/SKILL.md` at startup
  - Parse front-matter manifest (Pydantic dataclass `SkillManifest`: `name`, `description`, `triggers`, `script`)
  - Lazy injection: a `list_skills` tool returns names+descriptions; an `invoke_skill(name, args)` tool runs the skill's `script` via the bash tool
- Reference skill: `skills/echo/` — minimal example for tests

### Verification (per sub-phase)
- `tests/test_tools_<name>.py` — call the tool factory, assert the tool runs and emits a properly-shaped `HarnessEvent`
- E2E via `/run` with `tools: ["bash"]`, etc.

---

## Phase 5 — Filesystem Sources

**Why:** Tools (bash, file_search) need a sandbox dir. The dir's contents come from one of three sources, selected per request.

### Files
- `harness/filesystem/__init__.py` — `FilesystemConfig` discriminated union (Pydantic), `mount(config) -> Path` dispatcher
- `harness/filesystem/local.py` — symlink or copy `path` → sandbox dir
- `harness/filesystem/s3.py` — `boto3` download `s3://bucket/prefix` → sandbox dir; deps: `uv add boto3`
- `harness/filesystem/google_drive.py` — Google Drive API download `folder_id` → sandbox dir; deps: `uv add google-api-python-client google-auth`

Sandbox dir lifecycle: created in `tempfile.mkdtemp(prefix="harness-")`, cleaned up on stream end.

### Verification
- Unit tests with mocked S3 (`moto`) and Drive (mocked `googleapiclient`)
- E2E: POST `/run` with `filesystem: {"source": "local", "path": "./tests/fixtures/sample"}` + `tools: ["bash"]` and a prompt that asks the agent to `ls`

---

## Phase 6 — Configuration & DX

### Files
- `harness/cli.py` — `uv run harness <prompt>` for local interactive runs
- `pyproject.toml` — add `[project.scripts] harness = "harness.cli:main"`
- `Makefile` (or `justfile`) — `make dev`, `make test`, `make lint`
- `ruff.toml` — line length 100, target 3.14, select sensible defaults

### Verification
- `uv run harness "what files are in the sandbox?"` works end-to-end
- `uv run ruff check .` clean

---

## Phase 7 — Tests & CI

### Files
- `tests/conftest.py` — fixtures: `mock_litellm_client`, `tmp_sandbox`, `sample_skills_dir`
- `tests/test_*.py` — one per module, plus `tests/e2e/test_run_endpoint.py`
- `.github/workflows/ci.yml` — install uv, `uv sync`, `uv run ruff check .`, `uv run pytest`

### Verification
- `uv run pytest -q` — all green
- CI passes on PR

---

## Critical Files to Create or Modify

| File | Phase | Purpose |
|------|-------|---------|
| `src/utils.py` | 0 | LoggerSetup (loguru) |
| `src/settings.py` | 0 | Pydantic-dataclass Settings |
| `harness/stream.py` | 1 | `HarnessEvent`, SSE formatter, agent-event adapter |
| `harness/agent.py` | 2 | `AgentRunRequest`, `build_agent`, `run_streamed` |
| `harness/main.py` | 3 | FastAPI app + `/run` SSE endpoint |
| `harness/tools/{bash,file_search,web_search,mcp,skills}.py` | 4 | Tool factories |
| `harness/filesystem/{local,s3,google_drive}.py` | 5 | Sandbox mounting |
| `harness/cli.py` | 6 | CLI entry point |
| `tests/**` | 7 | Test suite |

## Reuse from existing code

- **`harness/litellm_factory.py`** — already provides `LiteLLMFactory.resolve_model()` and `.get_client()`. Used by `harness/agent.py` (Phase 2) to build the LiteLLM client passed to openai-agents.
- **`LoggerSetup` pattern** — `litellm_factory.py` already follows it; every new module gets `logger = LoggerSetup("ModuleName")` at the top.

## Conventions (from CLAUDE.md, enforced throughout)

- All inter-layer data → `pydantic.dataclasses.dataclass`
- All logging → `loguru` via `LoggerSetup`
- All commands → `uv run …`
- All commits → conventional commits (`feat:`, `fix:`, `chore:`, …)

## Out of scope (for now)

- Authentication / multi-tenancy
- Persistent run history / DB
- Frontend UI (consumer-side)
- Cost tracking and rate limiting
- Approval workflows for tool calls (openai-agents supports it; defer to v2)

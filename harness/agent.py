import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import docker
from agents import Runner
from agents.extensions.models.litellm_provider import LitellmProvider
from agents.run_config import RunConfig
from agents.sandbox import Manifest, SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import (
    Capabilities,
    LocalDirLazySkillSource,
    Memory,
    Skills,
)
from agents.sandbox.config import DEFAULT_PYTHON_SANDBOX_IMAGE
from agents.sandbox.entries import GitRepo, LocalDir
from agents.sandbox.sandboxes.docker import DockerSandboxClient, DockerSandboxClientOptions
from pydantic import Field
from pydantic.dataclasses import dataclass

from harness.filesystem import (
    FilesystemConfig,
    GitRepoFilesystemConfig,
    LocalFilesystemConfig,
    S3FilesystemConfig,
)
from harness.litellm_factory import LiteLLMFactory
from harness.sandbox_mounts import build_s3_mount
from harness.stream import HarnessEvent, from_agent_event
from harness.tools import resolve_tools
from src.utils import LoggerSetup

logger = LoggerSetup("AgentLoop")

WORKSPACE_INPUT_PATH = "input"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class AgentRunRequest:
    prompt: str
    model: str = "gemini/gemini-3-flash-preview"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    max_turns: int = 10
    filesystem: FilesystemConfig | None = None


def _build_manifest(fs: FilesystemConfig | None) -> Manifest:
    entries: dict[str | Path, Any] = {}
    if isinstance(fs, LocalFilesystemConfig) and fs.path:
        entries[WORKSPACE_INPUT_PATH] = LocalDir(src=Path(fs.path).resolve())
    elif isinstance(fs, S3FilesystemConfig) and fs.bucket:
        entries[WORKSPACE_INPUT_PATH] = build_s3_mount(fs)
    elif isinstance(fs, GitRepoFilesystemConfig) and fs.repo:
        entries[WORKSPACE_INPUT_PATH] = GitRepo(
            host=fs.host, repo=fs.repo, ref=fs.ref, subpath=fs.subpath
        )
    return Manifest(entries=entries)


def _build_capabilities() -> list[Any]:
    caps = list(Capabilities.default())
    if SKILLS_DIR.is_dir() and any(SKILLS_DIR.iterdir()):
        caps.append(
            Skills(
                lazy_from=LocalDirLazySkillSource(source=LocalDir(src=SKILLS_DIR)),
            )
        )
    caps.append(Memory())
    return caps


def build_agent(request: AgentRunRequest, host_tools: list[Any] | None = None) -> SandboxAgent:
    model = LiteLLMFactory.resolve_model(request.model)
    return SandboxAgent(
        name="harness-agent",
        instructions=request.system_prompt or "You are a helpful assistant.",
        model=model,
        tools=host_tools or [],
        default_manifest=_build_manifest(request.filesystem),
        capabilities=_build_capabilities(),
    )


def _build_sandbox_client() -> DockerSandboxClient:
    return DockerSandboxClient(
        docker.from_env(),
        options=DockerSandboxClientOptions(image=DEFAULT_PYTHON_SANDBOX_IMAGE),
    )


async def run_streamed(request: AgentRunRequest) -> AsyncIterator[HarnessEvent]:
    try:
        host_tools = resolve_tools(request.tools)
        agent = build_agent(request, host_tools=host_tools)

        logger.info("Starting sandbox agent run with model={model}", model=request.model)

        result = Runner.run_streamed(
            agent,
            input=request.prompt,
            run_config=RunConfig(
                model_provider=LitellmProvider(),
                sandbox=SandboxRunConfig(client=_build_sandbox_client()),
                tracing_disabled=True,
            ),
            max_turns=request.max_turns,
        )

        async for event in result.stream_events():
            harness_event = from_agent_event(event)
            if harness_event is not None:
                yield harness_event

    except Exception as e:
        logger.error("Agent run failed: {error}", error=e)
        yield HarnessEvent(
            event="error",
            data={"error": str(e), "type": type(e).__name__},
        )

    finally:
        yield HarnessEvent(event="done", data={})


if __name__ == "__main__":
    import asyncio

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello, who are you?"
    req = AgentRunRequest(prompt=prompt)

    async def main():
        async for event in run_streamed(req):
            if event.event == "message_delta":
                print(event.data.get("delta", ""), end="", flush=True)
            elif event.event == "done":
                print()

    asyncio.run(main())

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from agents import Agent, Runner
from agents.extensions.models.litellm_provider import LitellmProvider
from agents.run_config import RunConfig
from pydantic import Field
from pydantic.dataclasses import dataclass

from harness.filesystem import FilesystemConfig, cleanup, mount
from harness.litellm_factory import LiteLLMFactory
from harness.stream import HarnessEvent, from_agent_event
from src.utils import LoggerSetup

logger = LoggerSetup("AgentLoop")


@dataclass
class AgentRunRequest:
    prompt: str
    model: str = "gemini/gemini-3-flash-preview"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    max_turns: int = 10
    filesystem: FilesystemConfig | None = None


def build_agent(req: AgentRunRequest, tool_objects: list[Any] | None = None) -> Agent:
    model = LiteLLMFactory.resolve_model(req.model)
    return Agent(
        name="harness-agent",
        instructions=req.system_prompt or "You are a helpful assistant.",
        model=model,
        tools=tool_objects or [],
    )


async def run_streamed(req: AgentRunRequest) -> AsyncIterator[HarnessEvent]:
    from harness.tools import resolve_tools

    sandbox_dir: Path | None = None
    try:
        if req.filesystem is not None:
            sandbox_dir = await mount(req.filesystem)
            logger.info("Mounted sandbox at {dir}", dir=str(sandbox_dir))

        tool_kwargs = {"sandbox_dir": sandbox_dir} if sandbox_dir else {}
        tool_objects = resolve_tools(req.tools, **tool_kwargs)
        agent = build_agent(req, tool_objects=tool_objects)

        logger.info("Starting agent run with model={model}", model=req.model)

        result = Runner.run_streamed(
            agent,
            input=req.prompt,
            run_config=RunConfig(
                model_provider=LitellmProvider(),
                tracing_disabled=True,
            ),
            max_turns=req.max_turns,
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
        if sandbox_dir is not None:
            cleanup(sandbox_dir.parent if sandbox_dir.name == "workspace" else sandbox_dir)


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

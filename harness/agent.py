import sys
from collections.abc import AsyncIterator
from pathlib import Path

from agents import Agent, Runner
from agents.extensions.models.litellm_provider import LitellmProvider
from agents.run_config import RunConfig
from pydantic import Field
from pydantic.dataclasses import dataclass

from harness.litellm_factory import LiteLLMFactory
from harness.stream import HarnessEvent, from_agent_event
from harness.tools import resolve_tools
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("AgentLoop")


@dataclass
class AgentRunRequest:
    prompt: str
    model: str = "gemini/gemini-3-flash-preview"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    max_turns: int = 10
    mcp_config_path: Path | None = None
    tool_configs: dict[str, object] = Field(default_factory=dict)


def build_agent(request: AgentRunRequest) -> Agent:
    config_path = request.mcp_config_path or settings.mcp_config_path
    function_tools, mcp_servers = resolve_tools(
        request.tools,
        mcp_config_path=config_path,
        **request.tool_configs,
    )
    return Agent(
        name="harness-agent",
        instructions=request.system_prompt or "You are a helpful assistant.",
        model=LiteLLMFactory.resolve_model(request.model),
        tools=function_tools,
        mcp_servers=mcp_servers,
    )


async def run_streamed(request: AgentRunRequest) -> AsyncIterator[HarnessEvent]:
    try:
        agent = build_agent(request)

        logger.info("Starting agent run with model={model}", model=request.model)

        result = Runner.run_streamed(
            agent,
            input=request.prompt,
            run_config=RunConfig(
                model_provider=LitellmProvider(),
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

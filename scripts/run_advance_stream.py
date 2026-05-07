"""Test script: run the agent with shell + web_search tools and stream events.

Usage:
    uv run python scripts/run_advance_stream.py "What's the latest stable Python version?"
    uv run python scripts/run_advance_stream.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["LOG_LEVEL"] = "CRITICAL"

from loguru import logger as _loguru_logger  # noqa: E402

from harness.agent import AgentRunRequest, run_streamed  # noqa: E402
from harness.tools.filesystem import FilesystemConfig  # noqa: E402
from harness.tools.shell import ShellConfig  # noqa: E402

_loguru_logger.remove()

AGENT_WORKDIR = Path(r"C:\Users\ricar\repos\nexus\agent-harness\agent_workdir")


async def main():
    default_prompt = (
        "Use the shell to list the working directory. If any file looks like it "
        "hints at containing code, read it and show its contents to the user. "
        "Then append the one-liner 'agent was here' to that same file."
    )
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else default_prompt

    req = AgentRunRequest(
        prompt=prompt,
        model="gemini/gemini-3-flash-preview",
        tools=["shell", "web_search", "filesystem"],
        max_turns=30,
        tool_configs={
            "filesystem_config": FilesystemConfig(root=AGENT_WORKDIR),
            "shell_config": ShellConfig(cwd=AGENT_WORKDIR),
        },
    )

    print(f"--- Prompt ---\n{prompt}\n")

    async for event in run_streamed(req):
        if event.event == "message_delta":
            print(event.data.get("delta", ""), end="", flush=True)
        elif event.event == "message_done":
            print()
        elif event.event == "tool_called":
            name = event.data.get("name") or "tool"
            print(f"\n{name}({_format_args(event.data.get('arguments'))})")
        elif event.event == "tool_output":
            output = str(event.data.get("output", "")).rstrip()
            print(_indent(output))
        elif event.event == "error":
            print(f"\nerror: {event.data}")
        elif event.event == "done":
            print()


def _format_args(raw: object) -> str:
    if not raw:
        return ""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError, TypeError:
            return raw
    else:
        parsed = raw
    if isinstance(parsed, dict):
        if len(parsed) == 1:
            (value,) = parsed.values()
            return str(value)
        return ", ".join(f"{k}={v}" for k, v in parsed.items())
    return str(parsed)


def _indent(text: str, prefix: str = "  ") -> str:
    if not text:
        return ""
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    asyncio.run(main())

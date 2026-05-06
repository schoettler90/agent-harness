"""Test script: run the agent with gemini-3-flash-preview and print streamed events.

Usage:
    uv run python scripts/test_stream.py "What is the capital of France?"
    uv run python scripts/test_stream.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.agent import AgentRunRequest, run_streamed  # noqa: E402


async def main():
    prompt = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Explain quantum computing in 2 sentences."
    )

    req = AgentRunRequest(
        prompt=prompt,
        model="gemini/gemini-3-flash-preview",
        tools=[],
    )

    print(f"--- Streaming agent response for: {prompt!r} ---\n", file=sys.stderr)

    async for event in run_streamed(req):
        event_dict = {
            "event": event.event,
            "tool": event.tool,
            "data": event.data,
            "timestamp": event.timestamp,
        }
        print(json.dumps(event_dict))

        if event.event == "message_delta":
            print(event.data.get("delta", ""), end="", flush=True, file=sys.stderr)
        elif event.event == "error":
            print(f"\nERROR: {event.data}", file=sys.stderr)

    print("\n\n--- Done ---", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())

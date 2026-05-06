from __future__ import annotations

import asyncio
import sys

from harness.agent import AgentRunRequest, run_streamed
from src.settings import load_settings


def main():
    settings = load_settings()
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello!"

    req = AgentRunRequest(
        prompt=prompt,
        model=settings.model,
    )

    async def _run():
        async for event in run_streamed(req):
            if event.event == "message_delta":
                print(event.data.get("delta", ""), end="", flush=True)
            elif event.event == "message_done":
                print()
            elif event.event == "error":
                print(f"\nError: {event.data}", file=sys.stderr)
            elif event.event == "tool_called":
                tool_name = event.data.get("name", event.tool or "")
                print(f"\n[Tool: {tool_name}]", file=sys.stderr)
            elif event.event == "tool_output":
                output = str(event.data.get("output", ""))[:200]
                print(f"[Output] {output}", file=sys.stderr)

    asyncio.run(_run())


if __name__ == "__main__":
    main()

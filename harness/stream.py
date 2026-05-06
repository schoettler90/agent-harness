from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from agents.items import ItemHelpers, MessageOutputItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import (
    AgentUpdatedStreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)
from pydantic import Field
from pydantic.dataclasses import dataclass

EventType = Literal[
    "tool_called",
    "tool_output",
    "message_delta",
    "message_done",
    "error",
    "done",
]

ToolName = Literal["web_search", "file_search", "bash", "mcp", "skill"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class HarnessEvent:
    event: EventType
    tool: ToolName | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_now_iso)


def to_sse(event: HarnessEvent) -> str:
    payload = {
        "tool": event.tool,
        **event.data,
        "timestamp": event.timestamp,
    }
    return f"event: {event.event}\ndata: {json.dumps(payload)}\n\n"


def _classify_tool(name: str) -> ToolName | None:
    if not name:
        return None
    if "bash" in name or "shell" in name:
        return "bash"
    if "file_search" in name or "search_file" in name:
        return "file_search"
    if "web_search" in name:
        return "web_search"
    if "skill" in name:
        return "skill"
    if "mcp" in name:
        return "mcp"
    return None


def from_agent_event(raw: StreamEvent) -> HarnessEvent | None:
    if isinstance(raw, RawResponsesStreamEvent):
        data = raw.data
        if getattr(data, "type", None) == "response.output_text.delta":
            return HarnessEvent(
                event="message_delta",
                data={"delta": data.delta},
            )
        return None

    if isinstance(raw, RunItemStreamEvent):
        if raw.name == "tool_called" and isinstance(raw.item, ToolCallItem):
            raw_item = raw.item.raw_item
            tool_name = _classify_tool(getattr(raw_item, "name", "") or "")
            return HarnessEvent(
                event="tool_called",
                tool=tool_name,
                data={
                    "name": getattr(raw_item, "name", None),
                    "arguments": getattr(raw_item, "arguments", None),
                    "call_id": getattr(raw_item, "call_id", None),
                },
            )

        if raw.name == "tool_output" and isinstance(raw.item, ToolCallOutputItem):
            raw_item = raw.item.raw_item
            if isinstance(raw_item, dict):
                name_str = raw_item.get("name", "")
            else:
                name_str = getattr(raw_item, "name", "") or ""
            tool_name = _classify_tool(name_str)
            return HarnessEvent(
                event="tool_output",
                tool=tool_name,
                data={"output": str(raw.item.output)},
            )

        if raw.name == "message_output_created" and isinstance(raw.item, MessageOutputItem):
            text = ItemHelpers.text_message_output(raw.item)
            return HarnessEvent(
                event="message_done",
                data={"text": text},
            )

        return None

    if isinstance(raw, AgentUpdatedStreamEvent):
        return None

    return None

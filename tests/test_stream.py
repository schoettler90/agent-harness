from __future__ import annotations

import json
from unittest.mock import MagicMock

from harness.stream import HarnessEvent, _classify_tool, from_agent_event, to_sse


def test_harness_event_creation():
    event = HarnessEvent(event="message_delta", data={"delta": "hi"})
    assert event.event == "message_delta"
    assert event.tool is None
    assert event.data == {"delta": "hi"}
    assert event.timestamp


def test_to_sse_format():
    event = HarnessEvent(
        event="tool_called",
        tool="bash",
        data={"name": "bash", "arguments": '{"command": "ls"}'},
        timestamp="2026-01-01T00:00:00+00:00",
    )
    result = to_sse(event)
    assert result.startswith("event: tool_called\n")
    assert "data: " in result
    assert result.endswith("\n\n")

    data_line = result.split("data: ", 1)[1].split("\n")[0]
    payload = json.loads(data_line)
    assert payload["tool"] == "bash"
    assert payload["name"] == "bash"
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"


def test_to_sse_roundtrip():
    event = HarnessEvent(event="done", data={})
    sse = to_sse(event)
    lines = sse.strip().split("\n")
    assert lines[0] == "event: done"
    payload = json.loads(lines[1].removeprefix("data: "))
    assert payload["tool"] is None


def test_classify_tool():
    assert _classify_tool("bash") == "bash"
    assert _classify_tool("shell_exec") == "bash"
    assert _classify_tool("file_search") == "file_search"
    assert _classify_tool("web_search") == "web_search"
    assert _classify_tool("list_skills") == "skill"
    assert _classify_tool("read_skill") == "skill"
    assert _classify_tool("mcp_call") == "mcp"
    assert _classify_tool("") is None
    assert _classify_tool("unknown_tool") is None


def test_from_agent_event_text_delta():
    raw_data = MagicMock()
    raw_data.type = "response.output_text.delta"
    raw_data.delta = "Hello"

    from agents.stream_events import RawResponsesStreamEvent

    raw_event = RawResponsesStreamEvent(data=raw_data)
    result = from_agent_event(raw_event)

    assert result is not None
    assert result.event == "message_delta"
    assert result.data["delta"] == "Hello"


def test_from_agent_event_skips_other_raw():
    raw_data = MagicMock()
    raw_data.type = "response.created"

    from agents.stream_events import RawResponsesStreamEvent

    raw_event = RawResponsesStreamEvent(data=raw_data)
    result = from_agent_event(raw_event)
    assert result is None


def test_from_agent_event_agent_updated_returns_none():
    from agents.stream_events import AgentUpdatedStreamEvent

    mock_agent = MagicMock()
    raw_event = AgentUpdatedStreamEvent(new_agent=mock_agent)
    result = from_agent_event(raw_event)
    assert result is None

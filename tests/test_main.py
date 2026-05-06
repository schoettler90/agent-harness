from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from harness.main import app
from harness.stream import HarnessEvent


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_run_endpoint_returns_sse(client):
    mock_events = [
        HarnessEvent(event="message_delta", data={"delta": "Hi"}),
        HarnessEvent(event="done", data={}),
    ]

    async def mock_stream(req):
        for e in mock_events:
            yield e

    with patch("harness.main.run_streamed", side_effect=mock_stream):
        resp = client.post(
            "/run",
            json={"prompt": "hello", "model": "gemini/gemini-3-flash-preview", "tools": []},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: message_delta" in resp.text
    assert "event: done" in resp.text

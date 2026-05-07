import pytest

from harness.agent import AgentRunRequest


@pytest.fixture
def sample_agent_request():
    return AgentRunRequest(
        prompt="test",
        model="gemini/gemini-3-flash-preview",
        tools=[],
    )

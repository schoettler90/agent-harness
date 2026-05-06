from __future__ import annotations

import pytest

from harness.agent import AgentRunRequest


@pytest.fixture
def tmp_sandbox(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "test.txt").write_text("hello world")
    (sandbox / "notes.md").write_text("# Notes\nSome content here")
    return sandbox


@pytest.fixture
def sample_agent_request():
    return AgentRunRequest(
        prompt="test",
        model="gemini/gemini-3-flash-preview",
        tools=[],
    )


@pytest.fixture
def sample_skills_dir(tmp_path):
    skill_dir = tmp_path / "skills" / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: Echo tool for testing\n---\n# Echo\nRepeat input."
    )
    return tmp_path / "skills"

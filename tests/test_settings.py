import os
from pathlib import Path
from unittest.mock import patch

from src.settings import Settings, load_settings


def test_default_settings():
    s = Settings()
    assert s.model == "gemini/gemini-3-flash-preview"
    assert s.agent_workdir == Path("./agent_workdir")
    assert s.mcp_config_path == Path("mcp_config.json")
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.cors_origins == ["*"]
    assert s.log_level == "INFO"


def test_settings_from_env():
    env = {
        "MODEL": "gpt-4o",
        "AGENT_WORKDIR": "/tmp/test",
        "MCP_CONFIG_PATH": "/tmp/mcp.json",
        "HOST": "127.0.0.1",
        "PORT": "9000",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env):
        s = load_settings()
    assert s.model == "gpt-4o"
    assert s.agent_workdir == Path("/tmp/test")
    assert s.mcp_config_path == Path("/tmp/mcp.json")
    assert s.host == "127.0.0.1"
    assert s.port == 9000
    assert s.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    assert s.log_level == "DEBUG"

from __future__ import annotations

import os
from unittest.mock import patch

from src.settings import Settings, load_settings


def test_default_settings():
    s = Settings()
    assert s.model == "gemini/gemini-3-flash-preview"
    assert s.sandbox_dir == "./sandbox"
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.cors_origins == ["*"]
    assert s.log_level == "INFO"


def test_settings_from_env():
    env = {
        "MODEL": "gpt-4o",
        "SANDBOX_DIR": "/tmp/test",
        "HOST": "127.0.0.1",
        "PORT": "9000",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env):
        s = load_settings()
    assert s.model == "gpt-4o"
    assert s.sandbox_dir == "/tmp/test"
    assert s.host == "127.0.0.1"
    assert s.port == 9000
    assert s.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    assert s.log_level == "DEBUG"

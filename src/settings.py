import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic.dataclasses import dataclass

load_dotenv()


@dataclass
class Settings:
    model: str = Field(default="gemini/gemini-3-flash-preview")
    sandbox_dir: str = Field(default="./sandbox")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    log_level: str = Field(default="INFO")


def load_settings() -> Settings:
    return Settings(
        model=os.environ.get("MODEL", "gemini/gemini-3-flash-preview"),
        sandbox_dir=os.environ.get("SANDBOX_DIR", "./sandbox"),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        cors_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )


settings = load_settings()

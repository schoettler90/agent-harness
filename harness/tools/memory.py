import json
from pathlib import Path

from agents import function_tool

from harness.tools import register_tool
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("MemoryTool")


def _read_store(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("memory store unreadable, resetting: {e}", e=e)
        return {}


def _write_store(path: Path, store: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


@register_tool("memory")
def make_memory_tools(memory_path: Path | None = None, **_: object):
    store_path = Path(memory_path or (settings.agent_workdir / ".memory.json")).resolve()

    @function_tool(
        name_override="memory_save",
        description_override="Save a key/value pair to persistent memory.",
    )
    async def memory_save(key: str, value: str) -> str:
        """Save a value under a key.

        Args:
            key: Memory key.
            value: Value to store.
        """
        store = _read_store(store_path)
        store[key] = value
        _write_store(store_path, store)
        return f"Saved {key!r}"

    @function_tool(
        name_override="memory_load",
        description_override="Load a value by key, or list all keys if no key is given.",
    )
    async def memory_load(key: str | None = None) -> str:
        """Load from memory.

        Args:
            key: Key to look up. If omitted, returns all stored keys.
        """
        store = _read_store(store_path)
        if key is None:
            return "keys: " + ", ".join(sorted(store.keys())) if store else "(memory empty)"
        if key not in store:
            return f"(no value for {key!r})"
        return store[key]

    return [memory_save, memory_load]

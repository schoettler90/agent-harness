from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from agents import function_tool

from harness.tools import register_tool
from src.utils import LoggerSetup

logger = LoggerSetup("FileSearchTool")

_has_rg = shutil.which("rg") is not None


@register_tool("file_search")
def make_file_search_tool(sandbox_dir: Path | None = None):
    work_dir = sandbox_dir or Path("./sandbox")

    @function_tool(
        name_override="file_search",
        description_override=(
            "Search files by content pattern or list files"
            " matching a glob in the sandbox."
        ),
    )
    async def file_search(query: str, glob_filter: str = "*", max_results: int = 20) -> str:
        """Search files in the sandbox directory.

        Args:
            query: Text pattern to search for (regex supported with ripgrep)
            glob_filter: Glob pattern to filter files (e.g. '*.py')
            max_results: Maximum number of matching lines to return
        """
        logger.info("Searching for {query!r} in {dir}", query=query, dir=str(work_dir))

        if _has_rg:
            cmd = f'rg --max-count {max_results} --glob "{glob_filter}" "{query}" .'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
            )
            stdout, _ = await proc.communicate()
            return stdout.decode() or "No matches found."

        results: list[str] = []
        for p in work_dir.rglob(glob_filter):
            if p.is_file():
                try:
                    text = p.read_text(errors="ignore")
                    for i, line in enumerate(text.splitlines(), 1):
                        if query in line:
                            rel = p.relative_to(work_dir)
                            results.append(f"{rel}:{i}:{line.strip()}")
                            if len(results) >= max_results:
                                break
                except Exception:
                    pass
            if len(results) >= max_results:
                break
        return "\n".join(results) or "No matches found."

    return file_search

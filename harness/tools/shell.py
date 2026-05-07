import asyncio
from pathlib import Path

from agents import function_tool
from pydantic.dataclasses import dataclass

from harness.tools import register_tool
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("ShellTool")

DEFAULT_TIMEOUT_S = 120


@dataclass
class ShellConfig:
    """Config for the shell tool. `cwd` is the directory commands run in."""

    cwd: Path


@register_tool("shell")
def make_shell_tool(shell_config: ShellConfig | None = None, **_: object):
    cwd = shell_config.cwd if shell_config else settings.agent_workdir
    workdir = Path(cwd).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        description_override=(
            "Executes a shell command in the agent working directory and returns its output.\n\n"
            "IMPORTANT: Avoid using this tool to run commands when a dedicated tool exists."
            " Use the appropriate tool instead:\n"
            "  - File search: Use list_dir (NOT find or ls)\n"
            "  - Read files: Use read_file (NOT cat/head/tail)\n"
            "  - Edit files: Use update_file (NOT sed/awk)\n"
            "  - Write files: Use write_file (NOT echo/cat heredoc)\n\n"
            "Instructions:\n"
            "  - Always quote file paths that contain spaces with double quotes.\n"
            "  - Use absolute paths where possible to avoid working-directory confusion.\n"
            "  - Chain dependent commands with '&&'; use ';' when you don't care if"
            " earlier steps fail.\n"
            "  - The timeout parameter is in seconds (default 120, max 600).\n"
            "  - The description parameter is shown in logs — write a clear, concise"
            " summary of what the command does in active voice (e.g. 'Install dependencies',"
            " 'Run test suite')."
        ),
    )
    async def shell(command: str, description: str = "", timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Run a shell command in the agent working directory.

        Args:
            command: The shell command to execute.
            description: Short description of what the command does (used for logging).
            timeout: Timeout in seconds (default 120, max 600).
        """
        effective_timeout = max(1, min(600, timeout))
        label = description or command[:80]
        logger.info("shell: {label!r} (cwd={cwd})", label=label, cwd=workdir)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=effective_timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return f"Error: command timed out after {effective_timeout}s"
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            parts: list[str] = []
            if stdout:
                parts.append(stdout if stdout.endswith("\n") else stdout + "\n")
            if stderr:
                tail = stderr if stderr.endswith("\n") else stderr + "\n"
                parts.append(f"stderr:\n{tail}")
            parts.append(f"exit_code: {proc.returncode}")
            return "".join(parts)
        except Exception as e:
            logger.error("shell failed: {e}", e=e)
            return f"Error executing command: {e}"

    return shell

import asyncio
from pathlib import Path

from agents import function_tool
from pydantic import Field
from pydantic.dataclasses import dataclass

from harness.tools import register_tool
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("ShellTool")

DEFAULT_TIMEOUT_S = 60


@dataclass
class ShellConfig:
    """Config for the shell tool. `cwd` is the directory commands run in."""

    cwd: Path
    timeout_s: int = Field(default=DEFAULT_TIMEOUT_S)


@register_tool("shell")
def make_shell_tool(shell_config: ShellConfig | None = None, **_: object):
    cwd = shell_config.cwd if shell_config else settings.agent_workdir
    timeout_s = shell_config.timeout_s if shell_config else DEFAULT_TIMEOUT_S
    workdir = Path(cwd).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    @function_tool(
        name_override="shell",
        description_override=(
            "Execute a shell command in the agent working directory. "
            "Returns stdout, stderr, and exit_code."
        ),
    )
    async def shell(command: str) -> str:
        """Run a shell command.

        Args:
            command: The shell command to execute.
        """
        logger.info("shell exec: {cmd!r} (cwd={cwd})", cmd=command, cwd=str(workdir))
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return f"Error: command timed out after {timeout_s}s"
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            if proc.returncode == 0:
                return stdout if stdout else stderr
            parts = [s for s in (stdout, stderr) if s]
            body = "\n".join(parts) if parts else ""
            return f"{body}\n(exit {proc.returncode})" if body else f"(exit {proc.returncode})"
        except Exception as e:
            logger.error("shell failed: {e}", e=e)
            return f"Error executing command: {e}"

    return shell

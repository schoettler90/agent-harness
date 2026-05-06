import asyncio
from pathlib import Path

from agents import function_tool

from harness.tools import register_tool
from src.utils import LoggerSetup

logger = LoggerSetup("BashTool")


@register_tool("bash")
def make_bash_tool(sandbox_dir: Path | None = None):
    work_dir = str((sandbox_dir or Path("./sandbox")).resolve())

    @function_tool(
        name_override="bash",
        description_override=(
            "Execute a shell command in the sandbox directory."
            " Returns stdout, stderr, and exit code."
        ),
    )
    async def bash(command: str) -> str:
        """Execute a shell command.

        Args:
            command: The shell command to execute
        """
        logger.info("Executing: {command}", command=command)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            result = f"exit_code={proc.returncode}\nstdout:\n{stdout.decode()}"
            if stderr:
                result += f"\nstderr:\n{stderr.decode()}"
            return result
        except TimeoutError:
            return "Error: command timed out after 30 seconds"
        except Exception as e:
            return f"Error: {e}"

    return bash

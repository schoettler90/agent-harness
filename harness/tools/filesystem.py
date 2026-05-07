from pathlib import Path

from agents import function_tool
from agents.apply_diff import apply_diff
from agents.editor import ApplyPatchOperation, ApplyPatchResult
from pydantic.dataclasses import dataclass

from harness.tools import register_tool
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("FilesystemTool")


@dataclass
class FilesystemConfig:
    """Config for the filesystem tool. `root` is the agent's working directory."""

    root: Path


_BEGIN = "*** Begin Patch"
_END = "*** End Patch"
_ADD = "*** Add File: "
_DEL = "*** Delete File: "
_UPD = "*** Update File: "
_MOVE = "*** Move to: "


def _resolve_safe(root: Path, path: str) -> Path:
    if not path:
        raise ValueError("path is required")
    candidate = (root / path).resolve()
    root_resolved = root.resolve()
    if root_resolved != candidate and root_resolved not in candidate.parents:
        raise ValueError(f"Path {path!r} escapes the agent working directory")
    return candidate


class LocalApplyPatchEditor:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        target = _resolve_safe(self.root, op.path)
        if target.exists():
            return ApplyPatchResult(status="failed", output=f"Error: {op.path} already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            line[1:] if line.startswith("+") else line for line in (op.diff or "").splitlines()
        )
        if (op.diff or "").endswith("\n"):
            content += "\n"
        target.write_text(content, encoding="utf-8")
        return ApplyPatchResult(status="completed", output=f"Created {op.path}")

    def update_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        target = _resolve_safe(self.root, op.path)
        if not target.is_file():
            return ApplyPatchResult(status="failed", output=f"Error: {op.path} not found")
        original = target.read_text(encoding="utf-8")
        try:
            updated = apply_diff(original, op.diff or "")
        except ValueError as e:
            return ApplyPatchResult(status="failed", output=f"Error applying diff: {e}")
        if op.move_to:
            moved = _resolve_safe(self.root, op.move_to)
            moved.parent.mkdir(parents=True, exist_ok=True)
            moved.write_text(updated, encoding="utf-8")
            if moved != target:
                target.unlink()
            return ApplyPatchResult(
                status="completed", output=f"Updated and moved {op.path} -> {op.move_to}"
            )
        target.write_text(updated, encoding="utf-8")
        return ApplyPatchResult(status="completed", output=f"Updated {op.path}")

    def delete_file(self, op: ApplyPatchOperation) -> ApplyPatchResult:
        target = _resolve_safe(self.root, op.path)
        if not target.is_file():
            return ApplyPatchResult(status="failed", output=f"Error: {op.path} not found")
        target.unlink()
        return ApplyPatchResult(status="completed", output=f"Deleted {op.path}")


def _parse_patch(raw: str) -> list[ApplyPatchOperation]:
    lines = raw.splitlines()
    if not lines or lines[0] != _BEGIN or lines[-1] != _END:
        raise ValueError("Patch must start with '*** Begin Patch' and end with '*** End Patch'")
    ops: list[ApplyPatchOperation] = []
    i = 1
    while i < len(lines) - 1:
        line = lines[i]
        if line.startswith(_ADD):
            path = line[len(_ADD):].strip()
            i += 1
            diff_lines: list[str] = []
            while i < len(lines) - 1 and not _is_header(lines[i]):
                diff_lines.append(lines[i])
                i += 1
            ops.append(ApplyPatchOperation(type="create_file", path=path, diff="\n".join(diff_lines) + "\n"))
        elif line.startswith(_DEL):
            path = line[len(_DEL):].strip()
            i += 1
            ops.append(ApplyPatchOperation(type="delete_file", path=path))
        elif line.startswith(_UPD):
            path = line[len(_UPD):].strip()
            i += 1
            move_to: str | None = None
            if i < len(lines) - 1 and lines[i].startswith(_MOVE):
                move_to = lines[i][len(_MOVE):].strip()
                i += 1
            diff_lines = []
            while i < len(lines) - 1 and not _is_header(lines[i]):
                diff_lines.append(lines[i])
                i += 1
            ops.append(
                ApplyPatchOperation(
                    type="update_file",
                    path=path,
                    diff="\n".join(diff_lines) + "\n",
                    move_to=move_to,
                )
            )
        else:
            raise ValueError(f"Unexpected line in patch: {line!r}")
    return ops


def _is_header(line: str) -> bool:
    return line.startswith((_ADD, _DEL, _UPD))


@register_tool("filesystem")
def make_filesystem_tools(
    filesystem_config: FilesystemConfig | None = None, **_: object
):
    root = filesystem_config.root if filesystem_config else settings.agent_workdir
    workdir = Path(root).resolve()
    editor = LocalApplyPatchEditor(workdir)

    @function_tool(
        name_override="read_file",
        description_override=(
            "Reads a file from the local filesystem. You can access any file directly by using "
            "this tool. Assume this tool is able to read all files on the machine. If the User "
            "provides a path to a file assume that path is valid. It is okay to read a file "
            "that does not exist; an error will be returned.\n\n"
            "Usage:\n"
            "- The path parameter is resolved against the agent working directory.\n"
            "- By default, it reads up to 2000 lines starting from the beginning of the file.\n"
            "- When you already know which part of the file you need, only read that part. "
            "This can be important for larger files.\n"
            "- Results are returned using cat -n format, with line numbers starting at 1.\n"
            "- If you read a file that exists but has empty contents you will receive a system "
            "reminder warning in place of file contents.\n"
            "- Do NOT re-read a file you just edited to verify — write_file/update_file would "
            "have errored if the change failed."
        ),
    )
    async def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read a file with cat -n style line numbers.

        Args:
            path: File path resolved against the agent working directory.
            offset: 0-based line number to start reading from.
            limit: Maximum number of lines to return.
        """
        try:
            target = _resolve_safe(workdir, path)
            if not target.is_file():
                return f"Error: {path!r} is not a file"
            text = target.read_text(encoding="utf-8", errors="replace")
            if not text:
                return "(file is empty)"
            lines = text.splitlines()
            chunk = lines[offset : offset + limit]
            width = len(str(offset + len(chunk)))
            return "\n".join(f"{(offset + i + 1):>{width}}\t{line}" for i, line in enumerate(chunk))
        except Exception as e:
            return f"Error: {e}"

    @function_tool(
        name_override="write_file",
        description_override=(
            "Writes a file to the local filesystem.\n\n"
            "Usage:\n"
            "- This tool will overwrite the existing file if there is one at the provided path.\n"
            "- If this is an existing file, you MUST use the read_file tool first to read the "
            "file's contents. This tool will fail if you did not read the file first.\n"
            "- Prefer the update_file tool for modifying existing files — it only sends the "
            "diff. Only use this tool to create new files or for complete rewrites.\n"
            "- NEVER create documentation files (*.md) or README files unless explicitly "
            "requested by the User.\n"
            "- Only use emojis if the user explicitly requests it. Avoid writing emojis to "
            "files unless asked."
        ),
    )
    async def write_file(path: str, content: str) -> str:
        """Write content to a file (overwrites if it exists)."""
        try:
            target = _resolve_safe(workdir, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"Error: {e}"

    @function_tool(
        name_override="update_file",
        description_override=(
            "Performs exact string replacements in files.\n\n"
            "Usage:\n"
            "- You must use the read_file tool at least once in the conversation before "
            "editing. This tool will error if you attempt an edit without reading the file.\n"
            "- When editing text from read_file output, ensure you preserve the exact "
            "indentation (tabs/spaces) as it appears AFTER the line number prefix. The line "
            "number prefix format is: line number + tab. Everything after that is the actual "
            "file content to match. Never include any part of the line number prefix in the "
            "old_string or new_string.\n"
            "- ALWAYS prefer editing existing files. NEVER write new files unless explicitly "
            "required.\n"
            "- Only use emojis if the user explicitly requests it. Avoid adding emojis to "
            "files unless asked.\n"
            "- The edit will FAIL if old_string is not unique in the file. Either provide a "
            "larger string with more surrounding context to make it unique or use replace_all "
            "to change every instance of old_string.\n"
            "- Use replace_all for replacing and renaming strings across the file. This "
            "parameter is useful if you want to rename a variable for instance."
        ),
    )
    async def update_file(
        path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> str:
        """Replace `old_string` with `new_string` in a file.

        Args:
            path: File path resolved against the agent working directory.
            old_string: Exact text to find.
            new_string: Replacement text.
            replace_all: If true, replace every occurrence.
        """
        try:
            target = _resolve_safe(workdir, path)
            if not target.is_file():
                return f"Error: {path!r} is not a file"
            if old_string == new_string:
                return "Error: old_string and new_string are identical"
            original = target.read_text(encoding="utf-8")
            count = original.count(old_string)
            if count == 0:
                return f"Error: old_string not found in {path}"
            if count > 1 and not replace_all:
                return (
                    f"Error: old_string appears {count} times in {path}; "
                    "add more context to make it unique or pass replace_all=true"
                )
            updated = (
                original.replace(old_string, new_string)
                if replace_all
                else original.replace(old_string, new_string, 1)
            )
            target.write_text(updated, encoding="utf-8")
            replaced = count if replace_all else 1
            return f"Replaced {replaced} occurrence(s) in {path}"
        except Exception as e:
            return f"Error: {e}"

    @function_tool(
        name_override="apply_patch",
        description_override=(
            "Edit files using the v4a patch format.\n\n"
            "The input must be wrapped in '*** Begin Patch' / '*** End Patch'. "
            "Inside, use one or more file ops:\n"
            "  *** Add File: <path>     (followed by lines starting with +)\n"
            "  *** Delete File: <path>\n"
            "  *** Update File: <path>  (optional '*** Move to: <new>' then @@ hunks)\n\n"
            "Within Update hunks, lines start with ' ', '-', or '+'. Paths are relative "
            "to the agent working directory."
        ),
    )
    async def apply_patch(patch: str) -> str:
        """Apply a v4a patch to the agent working directory.

        Args:
            patch: The full patch text including '*** Begin Patch' / '*** End Patch'.
        """
        try:
            ops = _parse_patch(patch)
        except ValueError as e:
            return f"Error parsing patch: {e}"
        outputs: list[str] = []
        for op in ops:
            if op.type == "create_file":
                result = editor.create_file(op)
            elif op.type == "update_file":
                result = editor.update_file(op)
            elif op.type == "delete_file":
                result = editor.delete_file(op)
            else:
                result = ApplyPatchResult(status="failed", output=f"Unknown op {op.type}")
            if result.output:
                outputs.append(result.output)
        return "\n".join(outputs)

    return [read_file, write_file, update_file, apply_patch]

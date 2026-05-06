from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


async def mount_local(config) -> Path:
    source = Path(config.path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Local path does not exist: {source}")

    sandbox = Path(tempfile.mkdtemp(prefix="harness-"))
    workspace = sandbox / "workspace"

    if source.is_dir():
        shutil.copytree(source, workspace, dirs_exist_ok=True)
    else:
        workspace.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, workspace / source.name)

    return workspace

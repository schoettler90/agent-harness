import shutil
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Discriminator, Tag
from pydantic.dataclasses import dataclass

from src.utils import LoggerSetup

logger = LoggerSetup("Filesystem")


@dataclass
class LocalFilesystemConfig:
    source: Literal["local"] = "local"
    path: str = ""


@dataclass
class S3FilesystemConfig:
    source: Literal["s3"] = "s3"
    bucket: str = ""
    prefix: str = ""


@dataclass
class GoogleDriveFilesystemConfig:
    source: Literal["google_drive"] = "google_drive"
    folder_id: str = ""


FilesystemConfig = Annotated[
    Annotated[LocalFilesystemConfig, Tag("local")]
    | Annotated[S3FilesystemConfig, Tag("s3")]
    | Annotated[GoogleDriveFilesystemConfig, Tag("google_drive")],
    Discriminator("source"),
]

_AnyFsConfig = LocalFilesystemConfig | S3FilesystemConfig | GoogleDriveFilesystemConfig


async def mount(config: _AnyFsConfig) -> Path:
    logger.info("Mounting filesystem source={source}", source=config.source)

    if isinstance(config, LocalFilesystemConfig):
        from harness.filesystem.local import mount_local

        return await mount_local(config)
    if isinstance(config, S3FilesystemConfig):
        from harness.filesystem.s3 import mount_s3

        return await mount_s3(config)
    if isinstance(config, GoogleDriveFilesystemConfig):
        from harness.filesystem.google_drive import mount_gdrive

        return await mount_gdrive(config)
    raise ValueError(f"Unknown filesystem source: {config}")


def cleanup(sandbox_dir: Path) -> None:
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
        logger.info("Cleaned up sandbox: {dir}", dir=str(sandbox_dir))

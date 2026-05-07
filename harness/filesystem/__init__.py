from typing import Annotated, Literal

from pydantic import Discriminator, Tag
from pydantic.dataclasses import dataclass


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
class GitRepoFilesystemConfig:
    source: Literal["git"] = "git"
    repo: str = ""
    ref: str = "main"
    host: str = "github.com"
    subpath: str | None = None


FilesystemConfig = Annotated[
    Annotated[LocalFilesystemConfig, Tag("local")]
    | Annotated[S3FilesystemConfig, Tag("s3")]
    | Annotated[GitRepoFilesystemConfig, Tag("git")],
    Discriminator("source"),
]

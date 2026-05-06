from __future__ import annotations

import tempfile
from pathlib import Path


async def mount_s3(config) -> Path:
    import boto3

    sandbox = Path(tempfile.mkdtemp(prefix="harness-s3-"))
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=config.bucket, Prefix=config.prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel = key[len(config.prefix) :].lstrip("/")
            if not rel:
                continue
            dest = sandbox / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(config.bucket, key, str(dest))

    return sandbox

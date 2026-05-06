from __future__ import annotations

import os
import tempfile
from pathlib import Path


async def mount_gdrive(config) -> Path:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS", "")
    if not creds_path:
        raise ValueError("GOOGLE_DRIVE_CREDENTIALS env var not set")

    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    service = build("drive", "v3", credentials=creds)

    sandbox = Path(tempfile.mkdtemp(prefix="harness-gdrive-"))

    query = f"'{config.folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()

    for f in results.get("files", []):
        if f["mimeType"] == "application/vnd.google-apps.folder":
            continue
        request = service.files().get_media(fileId=f["id"])
        dest = sandbox / f["name"]
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    return sandbox

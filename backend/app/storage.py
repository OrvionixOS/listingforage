"""File storage. Local disk by default; swap StorageBackend for S3 in production."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import get_settings

settings = get_settings()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


class StorageBackend:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, user_id: str, file: UploadFile) -> tuple[str, str]:
        """Returns (upload_id, absolute_path). Enforces type + size limits."""
        if file.content_type not in ALLOWED_TYPES:
            raise ValueError(f"Unsupported file type: {file.content_type}")
        data = await file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"File exceeds {settings.max_upload_mb}MB limit")
        upload_id = uuid.uuid4().hex
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
        user_dir = self.root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{upload_id}{ext}"
        path.write_bytes(data)
        return upload_id, str(path)

    def path_for(self, stored_path: str) -> Path:
        return Path(stored_path)


storage = StorageBackend(settings.storage_dir)

"""File storage. Local disk by default; swap StorageBackend for S3 in production."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import get_settings

settings = get_settings()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# product-file assets the AI can analyze for listing accuracy
ASSET_TYPES = {
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "image/svg+xml": ".svg",
}

_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", **ASSET_TYPES}


class StorageBackend:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, user_id: str, file: UploadFile,
                          allow_assets: bool = False) -> tuple[str, str]:
        """Returns (upload_id, absolute_path). Enforces type + size limits.
        With allow_assets, product files (PDF/ZIP/SVG) are accepted too."""
        allowed = (ALLOWED_TYPES | set(ASSET_TYPES)) if allow_assets else ALLOWED_TYPES
        if file.content_type not in allowed:
            raise ValueError(f"Unsupported file type: {file.content_type}")
        data = await file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"File exceeds {settings.max_upload_mb}MB limit")
        upload_id = uuid.uuid4().hex
        ext = _EXT[file.content_type]
        user_dir = self.root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{upload_id}{ext}"
        path.write_bytes(data)
        return upload_id, str(path)

    def path_for(self, stored_path: str) -> Path:
        return Path(stored_path)


storage = StorageBackend(settings.storage_dir)

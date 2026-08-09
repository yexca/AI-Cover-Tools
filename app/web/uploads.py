from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .formats import AUDIO_EXTENSIONS
from .paths import UPLOADS_DIR


_UPLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{64}\.[a-z0-9]+$")


class AudioUploadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AudioUploadStore:
    def __init__(self, directory: Path = UPLOADS_DIR) -> None:
        self.directory = directory

    async def save(self, filename: str, chunks: AsyncIterator[bytes]) -> dict[str, Any]:
        display_name = self._display_name(filename)
        suffix = Path(display_name).suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise AudioUploadError("unsupported_audio_file", f"Unsupported audio file type: {suffix or display_name}")

        self.directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, temporary = tempfile.mkstemp(prefix=".audio-upload-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    stream.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if size == 0:
                raise AudioUploadError("empty_audio_file", "The selected audio file is empty.")

            upload_id = f"{digest.hexdigest()}{suffix}"
            target = self.directory / upload_id
            reused = target.exists()
            if reused:
                os.unlink(temporary)
            else:
                os.replace(temporary, target)
            return {"id": upload_id, "name": display_name, "size": size, "reused": reused}
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def resolve(self, upload_id: str) -> Path:
        value = str(upload_id or "").strip().lower()
        if not _UPLOAD_ID_PATTERN.fullmatch(value) or Path(value).suffix not in AUDIO_EXTENSIONS:
            raise AudioUploadError("invalid_upload_id", "The workflow contains an invalid audio upload reference.")
        root = self.directory.resolve()
        path = (root / value).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise AudioUploadError(
                "invalid_upload_id",
                "The workflow contains an invalid audio upload reference.",
            ) from exc
        if not path.is_file():
            raise AudioUploadError("uploaded_audio_missing", f"Uploaded audio file does not exist: {value}")
        return path

    @staticmethod
    def _display_name(filename: str) -> str:
        value = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not value or value in {".", ".."} or any(ord(character) < 32 for character in value):
            raise AudioUploadError("invalid_audio_filename", "The selected audio file has an invalid filename.")
        return value

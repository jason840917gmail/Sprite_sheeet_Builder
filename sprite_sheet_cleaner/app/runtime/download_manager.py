from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
from typing import Callable
from urllib.request import Request, urlopen


ProgressCallback = Callable[[float], None]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(
    url: str,
    destination: str | Path,
    expected_sha256: str,
    *,
    progress: ProgressCallback | None = None,
    opener=urlopen,
) -> Path:
    if len(expected_sha256) != 64:
        raise ValueError("Expected checksum must be a SHA-256 hex digest.")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".download", dir=target.parent)
    import os

    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        request = Request(url, headers={"User-Agent": "SpriteSheetCleaner/0.1"})
        with opener(request) as response, temporary.open("wb") as output:
            total = int(response.headers.get("Content-Length", "0") or 0)
            received = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                received += len(chunk)
                if progress is not None and total:
                    progress(min(received / total, 1.0))
        if sha256_file(temporary).lower() != expected_sha256.lower():
            raise ValueError("Downloaded file checksum does not match the manifest.")
        temporary.replace(target)
        if progress is not None:
            progress(1.0)
        return target
    finally:
        if temporary.exists():
            temporary.unlink()

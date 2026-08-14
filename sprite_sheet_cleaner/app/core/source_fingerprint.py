from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


IMAGE_FINGERPRINT_KIND = "rgba-sha256-v1"
VIDEO_FINGERPRINT_KIND = "file-sha256-v1"


def fingerprint_image(image: Image.Image) -> tuple[str, str]:
    """Return the stable decoded-pixel fingerprint used by source identity."""
    rgba = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(f"{rgba.width}x{rgba.height}:RGBA".encode("ascii"))
    digest.update(rgba.tobytes())
    return IMAGE_FINGERPRINT_KIND, digest.hexdigest()


def fingerprint_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> tuple[str, str]:
    """Hash a media file without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return VIDEO_FINGERPRINT_KIND, digest.hexdigest()

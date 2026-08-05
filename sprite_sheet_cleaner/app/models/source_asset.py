from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from PIL import Image


@dataclass(frozen=True, slots=True)
class SourceAsset:
    path: str | None
    fingerprint: str
    size: tuple[int, int]

    @classmethod
    def from_image(cls, image: Image.Image, path: str | Path | None = None) -> "SourceAsset":
        rgba = image.convert("RGBA")
        digest = hashlib.sha256()
        digest.update(f"{rgba.width}x{rgba.height}:RGBA".encode("ascii"))
        digest.update(rgba.tobytes())
        return cls(
            path=str(Path(path)) if path is not None else None,
            fingerprint=digest.hexdigest(),
            size=rgba.size,
        )

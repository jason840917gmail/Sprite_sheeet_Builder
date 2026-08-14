from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.core.source_fingerprint import IMAGE_FINGERPRINT_KIND, fingerprint_image


@dataclass(frozen=True, slots=True)
class SourceAsset:
    path: str | None
    fingerprint: str
    size: tuple[int, int]
    fingerprint_kind: str = IMAGE_FINGERPRINT_KIND

    @classmethod
    def from_image(cls, image: Image.Image, path: str | Path | None = None) -> "SourceAsset":
        rgba = image.convert("RGBA")
        _kind, fingerprint = fingerprint_image(rgba)
        return cls(
            path=str(Path(path)) if path is not None else None,
            fingerprint=fingerprint,
            size=rgba.size,
            fingerprint_kind=_kind,
        )

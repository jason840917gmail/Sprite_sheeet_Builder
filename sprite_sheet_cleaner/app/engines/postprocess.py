from __future__ import annotations

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.engines.base import MatteResult


def apply_matte(image: Image.Image, result: MatteResult) -> Image.Image:
    """Apply a uint8 matte while preserving the source alpha channel."""
    rgba = np.array(image.convert("RGBA"), dtype=np.uint16, copy=True)
    result.validated(image)
    source_alpha = rgba[:, :, 3]
    rgba[:, :, 3] = (source_alpha * result.matte.astype(np.uint16) + 127) // 255
    return Image.fromarray(rgba.astype(np.uint8), "RGBA")

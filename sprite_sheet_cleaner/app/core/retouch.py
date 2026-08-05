from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


RetouchMode = Literal["erase", "paint", "clone"]
RGBColor = tuple[int, int, int]
Point = tuple[int, int]


def apply_retouch_stroke(
    image: Image.Image,
    points: list[Point],
    *,
    mode: RetouchMode,
    radius: int | None = None,
    diameter: int | None = None,
    opacity: float = 1.0,
    color: RGBColor = (255, 0, 255),
    clone_origin: Point | None = None,
    clone_anchor: Point | None = None,
    source_image: Image.Image | None = None,
) -> Image.Image:
    """Apply an alpha erase or solid-color stroke to an RGBA image.

    ``clone`` is retained as the UI mode name for compatibility, but it now
    paints the selected RGB color exactly like ``paint``. The previous
    offset-based source-image arguments are accepted for project/API
    compatibility and intentionally ignored.
    """
    if mode not in {"erase", "paint", "clone"}:
        raise ValueError(f"Unsupported retouch mode: {mode}")
    if radius is None and diameter is None:
        raise ValueError("Retouch brush radius or diameter is required.")
    if radius is not None and radius <= 0:
        raise ValueError("Retouch brush radius must be positive.")
    if diameter is not None and diameter <= 0:
        raise ValueError("Retouch brush diameter must be positive.")
    if not points:
        return image.convert("RGBA").copy()
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("Retouch opacity must be between 0 and 1.")
    if len(color) != 3 or any(channel < 0 or channel > 255 for channel in color):
        raise ValueError("Retouch color must contain three channels between 0 and 255.")
    target = image.convert("RGBA").copy()
    target_array = np.array(target, dtype=np.float32)
    height, width = target_array.shape[:2]

    for point_x, point_y in points:
        mask = _brush_mask((width, height), (point_x, point_y), radius, opacity, diameter=diameter)
        if not np.any(mask):
            continue
        if mode == "erase":
            target_array[:, :, 3] *= 1.0 - mask
            continue

        if mode in {"paint", "clone"}:
            source_rgb = np.array(color, dtype=np.float32)
            target_array[:, :, :3] = (
                target_array[:, :, :3] * (1.0 - mask[:, :, None])
                + source_rgb[None, None, :] * mask[:, :, None]
            )
            continue

    target_array = np.clip(target_array, 0, 255).astype(np.uint8)
    return Image.fromarray(target_array, mode="RGBA")


def _brush_mask(
    size: tuple[int, int],
    center: Point,
    radius: int | None,
    opacity: float,
    *,
    diameter: int | None = None,
) -> np.ndarray:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    x, y = center
    fill = round(opacity * 255)
    if diameter is not None:
        if diameter == 1:
            # A one-pixel brush must never expand into a 3x3 ellipse.
            draw.point((x, y), fill=fill)
        else:
            half_extent = (diameter - 1) / 2.0
            draw.ellipse(
                (x - half_extent, y - half_extent, x + half_extent, y + half_extent),
                fill=fill,
            )
    else:
        assert radius is not None
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    should_blur = (diameter is not None and diameter >= 6) or (
        diameter is None and radius is not None and radius >= 3
    )
    if should_blur:
        blur_radius = diameter * 0.09 if diameter is not None else radius * 0.18
        mask = mask.filter(ImageFilter.GaussianBlur(max(0.5, blur_radius)))
    return np.asarray(mask, dtype=np.float32) / 255.0

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
    """Apply an alpha erase, solid-color paint, or RGB clone stroke to an RGBA image."""
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
    if mode == "clone" and (clone_origin is None or clone_anchor is None):
        raise ValueError("Clone mode requires a source point and stroke anchor.")

    target = image.convert("RGBA").copy()
    source = (source_image or target).convert("RGBA").copy()
    target_array = np.array(target, dtype=np.float32)
    source_array = np.array(source, dtype=np.float32)
    height, width = target_array.shape[:2]
    anchor_x, anchor_y = clone_anchor or points[0]
    origin_x, origin_y = clone_origin or (0, 0)

    for point_x, point_y in points:
        mask = _brush_mask((width, height), (point_x, point_y), radius, opacity, diameter=diameter)
        if not np.any(mask):
            continue
        if mode == "erase":
            target_array[:, :, 3] *= 1.0 - mask
            continue

        if mode == "paint":
            source_rgb = np.array(color, dtype=np.float32)
            target_array[:, :, :3] = (
                target_array[:, :, :3] * (1.0 - mask[:, :, None])
                + source_rgb[None, None, :] * mask[:, :, None]
            )
            continue

        offset_x = origin_x - anchor_x
        offset_y = origin_y - anchor_y
        y_grid, x_grid = np.indices((height, width))
        source_x = x_grid + offset_x
        source_y = y_grid + offset_y
        valid = (
            (source_x >= 0)
            & (source_x < source_array.shape[1])
            & (source_y >= 0)
            & (source_y < source_array.shape[0])
        )
        effective_mask = mask * valid
        sampled = np.zeros_like(target_array[:, :, :3])
        sampled[valid] = source_array[source_y[valid], source_x[valid], :3]
        target_array[:, :, :3] = (
            target_array[:, :, :3] * (1.0 - effective_mask[:, :, None])
            + sampled * effective_mask[:, :, None]
        )

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

from __future__ import annotations

import math

from PIL import Image

from sprite_sheet_cleaner.app.core.alpha_ops import transform_premultiplied
from sprite_sheet_cleaner.app.core.bucket_renderer import finalize_bucket_image
from sprite_sheet_cleaner.app.models.bucket_settings import BucketSettings
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform, normalize_angle


def snap_angle(angle_degrees: float, increment: float = 15.0) -> float:
    if increment <= 0 or not math.isfinite(increment):
        raise ValueError("Snap increment must be a positive finite number.")
    return normalize_angle(round(float(angle_degrees) / increment) * increment)


def angle_between_points(
    pivot: tuple[float, float],
    start: tuple[float, float],
    current: tuple[float, float],
) -> float:
    start_angle = math.degrees(math.atan2(start[1] - pivot[1], start[0] - pivot[0]))
    current_angle = math.degrees(math.atan2(current[1] - pivot[1], current[0] - pivot[0]))
    return normalize_angle(current_angle - start_angle)


def _inverse_affine(
    size: tuple[int, int],
    transform: TileTransform,
) -> tuple[float, float, float, float, float, float]:
    width, height = size
    pivot_x = transform.pivot_x * width
    pivot_y = transform.pivot_y * height
    radians = math.radians(transform.angle_degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    a = cosine / transform.scale_x
    b = sine / transform.scale_x
    d = -sine / transform.scale_y
    e = cosine / transform.scale_y
    c = pivot_x - a * pivot_x - b * pivot_y
    f = pivot_y - d * pivot_x - e * pivot_y
    return a, b, c, d, e, f


def render_tile_transform(
    base_image: Image.Image,
    settings: BucketSettings,
    transform: TileTransform,
) -> Image.Image:
    settings.validated()
    transform = transform.copy().validated()
    target = (settings.tile_width, settings.tile_height)
    if base_image.size != target:
        raise ValueError("Tile base does not match the configured bucket dimensions.")
    if (
        transform.scale_x == 1.0
        and transform.scale_y == 1.0
        and transform.angle_degrees == 0.0
    ):
        rendered = base_image.convert("RGBA").copy()
    else:
        rendered = transform_premultiplied(
            base_image,
            target,
            _inverse_affine(target, transform),
            transform.resample_mode or settings.resample_mode,
        )
    return finalize_bucket_image(rendered, settings)

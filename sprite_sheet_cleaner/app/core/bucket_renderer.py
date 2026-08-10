from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.core.alpha_ops import dilate_transparent_rgb, resize_premultiplied
from sprite_sheet_cleaner.app.models.bucket_settings import BucketSettings


def _placement(
    canvas_size: tuple[int, int],
    image_size: tuple[int, int],
    settings: BucketSettings,
) -> tuple[int, int]:
    canvas_width, canvas_height = canvas_size
    width, height = image_size
    x = (canvas_width - width) // 2
    if settings.anchor == "bottom-center":
        y = canvas_height - settings.padding - height
    else:
        y = (canvas_height - height) // 2
    return x, y


def prepare_bucket_base(image: Image.Image, settings: BucketSettings) -> Image.Image:
    """Normalize content onto an exact, untransformed bucket canvas."""
    settings.validated()
    rgba = image.convert("RGBA")
    canvas_size = (settings.tile_width, settings.tile_height)
    inner_width = max(1, settings.tile_width - settings.padding * 2)
    inner_height = max(1, settings.tile_height - settings.padding * 2)
    target_inner = (inner_width, inner_height)
    width, height = rgba.size
    if width <= 0 or height <= 0:
        raise ValueError("Cannot add an empty image to the bucket.")

    if settings.resize_mode == "stretch":
        prepared = resize_premultiplied(rgba, target_inner, settings.resample_mode)
    elif settings.resize_mode in {"fit", "fit_down_only"}:
        scale = min(inner_width / width, inner_height / height)
        if settings.resize_mode == "fit_down_only":
            scale = min(scale, 1.0)
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        prepared = (
            rgba.copy()
            if new_size == rgba.size
            else resize_premultiplied(rgba, new_size, settings.resample_mode)
        )
    elif settings.resize_mode == "fill":
        scale = max(inner_width / width, inner_height / height)
        resized = resize_premultiplied(
            rgba,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            settings.resample_mode,
        )
        left = max(0, (resized.width - inner_width) // 2)
        if settings.anchor == "bottom-center":
            top = max(0, resized.height - inner_height)
        else:
            top = max(0, (resized.height - inner_height) // 2)
        prepared = resized.crop((left, top, left + inner_width, top + inner_height))
    else:
        prepared = rgba.copy()

    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x, y = _placement(canvas_size, prepared.size, settings)
    canvas.paste(prepared, (x, y))
    return canvas


def finalize_bucket_image(image: Image.Image, settings: BucketSettings) -> Image.Image:
    settings.validated()
    if image.size != (settings.tile_width, settings.tile_height):
        raise ValueError("Rendered tile does not match the configured bucket dimensions.")
    return dilate_transparent_rgb(image.convert("RGBA"), radius=settings.edge_bleed)

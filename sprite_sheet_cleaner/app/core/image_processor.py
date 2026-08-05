from __future__ import annotations

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.core.alpha_ops import dilate_transparent_rgb, resize_premultiplied
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings
from sprite_sheet_cleaner.app.core.frame_resizer import resize_frame


CropRect = tuple[int, int, int, int]


def clamp_crop_rect(source_image: Image.Image, crop_rect: CropRect) -> CropRect:
    x, y, width, height = (int(value) for value in crop_rect)
    if width <= 0 or height <= 0:
        raise ValueError("Crop rectangle must have positive width and height.")

    left = max(0, x)
    top = max(0, y)
    right = min(source_image.width, x + width)
    bottom = min(source_image.height, y + height)

    if right <= left or bottom <= top:
        raise ValueError("Crop rectangle is outside the source image.")

    return left, top, right - left, bottom - top


def crop_source_image(source_image: Image.Image, crop_rect: CropRect) -> Image.Image:
    x, y, width, height = clamp_crop_rect(source_image, crop_rect)
    return source_image.crop((x, y, x + width, y + height)).convert("RGBA")


def remove_background_color(
    image: Image.Image,
    background_color: tuple[int, int, int],
    tolerance: int,
) -> Image.Image:
    rgba = image.convert("RGBA")
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative.")

    pixels = np.array(rgba, dtype=np.uint8, copy=True)
    rgb = pixels[:, :, :3].astype(np.int32)
    background = np.array(background_color, dtype=np.int32)
    distance = np.sqrt(np.sum((rgb - background) ** 2, axis=2))
    pixels[:, :, 3] = np.where(distance <= tolerance, 0, pixels[:, :, 3])
    return Image.fromarray(pixels, "RGBA")


def trim_transparent_edges(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return rgba.crop(bbox)


def scale_to_settings(image: Image.Image, settings: AppSettings) -> Image.Image:
    settings.validated()
    if settings.scale_mode == "none":
        return image

    max_width = max(1, settings.tile_width - settings.padding * 2)
    max_height = max(1, settings.tile_height - settings.padding * 2)
    width, height = image.size
    scale = min(max_width / width, max_height / height)

    if settings.scale_mode == "scale_down_only" and scale >= 1:
        return image

    scale = min(scale, 1) if settings.scale_mode == "scale_down_only" else scale
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if new_size == image.size:
        return image
    return resize_premultiplied(image, new_size)


def place_on_tile_canvas(image: Image.Image, settings: AppSettings) -> Image.Image:
    settings.validated()
    tile = Image.new(
        "RGBA",
        (settings.tile_width, settings.tile_height),
        (0, 0, 0, 0),
    )

    width, height = image.size
    x = (settings.tile_width - width) // 2
    if settings.anchor == "bottom-center":
        y = settings.tile_height - settings.padding - height
    else:
        y = (settings.tile_height - height) // 2

    tile.paste(image, (x, y))
    return dilate_transparent_rgb(tile, radius=settings.edge_bleed)


def process_crop(
    source_image: Image.Image,
    crop_rect: CropRect,
    settings: AppSettings,
) -> Image.Image:
    settings.validated()
    crop = crop_source_image(source_image, crop_rect)

    if settings.remove_background:
        crop = remove_background_color(
            crop,
            settings.background_color,
            settings.tolerance,
        )

    if settings.trim_transparent:
        crop = trim_transparent_edges(crop)

    crop = scale_to_settings(crop, settings)
    return place_on_tile_canvas(crop, settings)


def process_crop_with_resize(
    source_image: Image.Image,
    crop_rect: CropRect,
    settings: AppSettings,
    resize_settings: FrameResizeSettings | None = None,
) -> Image.Image:
    """Process a crop and optionally resize it to an exact intermediate frame canvas."""
    settings.validated()
    crop = crop_source_image(source_image, crop_rect)

    if settings.remove_background:
        crop = remove_background_color(crop, settings.background_color, settings.tolerance)

    if settings.trim_transparent:
        crop = trim_transparent_edges(crop)

    if resize_settings is not None:
        crop = resize_frame(crop, resize_settings)

    crop = scale_to_settings(crop, settings)
    return place_on_tile_canvas(crop, settings)

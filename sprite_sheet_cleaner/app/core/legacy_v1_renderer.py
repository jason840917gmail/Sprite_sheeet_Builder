from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, remove_background_color, trim_transparent_edges
from sprite_sheet_cleaner.app.models.app_settings import AppSettings


def render_legacy_tile(source_image: Image.Image, crop_rect: tuple[int, int, int, int], settings: AppSettings) -> Image.Image:
    """Reproduce the pre-revision tile renderer only for legacy project migration."""
    x, y, width, height = clamp_crop_rect(source_image, crop_rect)
    image = source_image.crop((x, y, x + width, y + height)).convert("RGBA")
    if settings.remove_background:
        image = remove_background_color(image, settings.background_color, settings.tolerance)
    if settings.trim_transparent:
        image = trim_transparent_edges(image)
    if settings.scale_mode != "none":
        max_width = max(1, settings.tile_width - settings.padding * 2)
        max_height = max(1, settings.tile_height - settings.padding * 2)
        scale = min(max_width / image.width, max_height / image.height)
        if settings.scale_mode == "scale_down_only" and scale >= 1:
            scale = 1
        if settings.scale_mode == "scale_down_only":
            scale = min(scale, 1)
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        if new_size != image.size:
            image = image.resize(new_size, Image.Resampling.LANCZOS)

    tile = Image.new("RGBA", (settings.tile_width, settings.tile_height), (0, 0, 0, 0))
    destination_x = (settings.tile_width - image.width) // 2
    if settings.anchor == "bottom-center":
        destination_y = settings.tile_height - settings.padding - image.height
    else:
        destination_y = (settings.tile_height - image.height) // 2
    tile.paste(image, (destination_x, destination_y), image)
    return tile

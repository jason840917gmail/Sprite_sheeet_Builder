from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.core.alpha_ops import resize_premultiplied
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings


def resize_frame(image: Image.Image, settings: FrameResizeSettings) -> Image.Image:
    """Resize an image to an exact canvas while keeping the requested mode."""
    settings.validated()
    rgba = image.convert("RGBA")
    target = (settings.target_width, settings.target_height)

    if settings.mode == "stretch":
        return resize_premultiplied(rgba, target)

    width, height = rgba.size
    if width <= 0 or height <= 0:
        raise ValueError("Cannot resize an empty frame.")

    if settings.mode == "fit":
        scale = min(settings.target_width / width, settings.target_height / height)
    else:  # fill: preserve aspect ratio, then crop the overflow.
        scale = max(settings.target_width / width, settings.target_height / height)

    resized = resize_premultiplied(
        rgba,
        (max(1, round(width * scale)), max(1, round(height * scale))),
    )

    if settings.mode == "fit":
        canvas = Image.new("RGBA", target, (0, 0, 0, 0))
        x = (settings.target_width - resized.width) // 2
        y = (settings.target_height - resized.height) // 2
        canvas.paste(resized, (x, y))
        return canvas

    left = max(0, (resized.width - settings.target_width) // 2)
    top = max(0, (resized.height - settings.target_height) // 2)
    return resized.crop((left, top, left + settings.target_width, top + settings.target_height))


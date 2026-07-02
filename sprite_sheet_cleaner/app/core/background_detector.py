from __future__ import annotations

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.core.image_processor import CropRect, clamp_crop_rect


def detect_background_color(
    source_image: Image.Image,
    crop_rect: CropRect | None = None,
    *,
    border_width: int = 12,
    bin_size: int = 8,
) -> tuple[int, int, int]:
    if border_width <= 0:
        raise ValueError("Border width must be positive.")
    if bin_size <= 0:
        raise ValueError("Bin size must be positive.")

    sample = _sample_selection_border(source_image, crop_rect, border_width) if crop_rect else _sample_image_border(source_image)
    if sample.size == 0:
        raise ValueError("No pixels were available for background detection.")

    return _dominant_quantized_color(sample, bin_size)


def _sample_selection_border(source_image: Image.Image, crop_rect: CropRect, border_width: int) -> np.ndarray:
    x, y, width, height = clamp_crop_rect(source_image, crop_rect)
    crop = source_image.crop((x, y, x + width, y + height)).convert("RGBA")
    pixels = np.array(crop, dtype=np.uint8)
    border = min(border_width, max(1, width // 2), max(1, height // 2))

    mask = np.zeros((height, width), dtype=bool)
    mask[:border, :] = True
    mask[-border:, :] = True
    mask[:, :border] = True
    mask[:, -border:] = True
    return _visible_rgb_pixels(pixels, mask)


def _sample_image_border(source_image: Image.Image) -> np.ndarray:
    image = source_image.convert("RGBA")
    width, height = image.size
    pixels = np.array(image, dtype=np.uint8)
    border = min(32, max(1, width // 8), max(1, height // 8))

    mask = np.zeros((height, width), dtype=bool)
    mask[:border, :] = True
    mask[-border:, :] = True
    mask[:, :border] = True
    mask[:, -border:] = True
    return _visible_rgb_pixels(pixels, mask)


def _visible_rgb_pixels(rgba_pixels: np.ndarray, mask: np.ndarray) -> np.ndarray:
    alpha_mask = rgba_pixels[:, :, 3] > 0
    combined_mask = mask & alpha_mask
    return rgba_pixels[:, :, :3][combined_mask]


def _dominant_quantized_color(rgb_pixels: np.ndarray, bin_size: int) -> tuple[int, int, int]:
    quantized = rgb_pixels.astype(np.uint16) // bin_size
    _unique, inverse, counts = np.unique(quantized, axis=0, return_inverse=True, return_counts=True)
    dominant_index = int(np.argmax(counts))
    dominant_mask = inverse == dominant_index
    color = np.round(np.mean(rgb_pixels[dominant_mask], axis=0)).astype(int)
    return tuple(int(channel) for channel in color)

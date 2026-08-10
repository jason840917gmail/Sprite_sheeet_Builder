from __future__ import annotations

from PIL import Image
import numpy as np


def resize_premultiplied(
    image: Image.Image,
    size: tuple[int, int],
    resample_mode: str = "smooth",
) -> Image.Image:
    """Resize straight-alpha RGBA without pulling hidden RGB into edges."""
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("Resize dimensions must be positive.")

    if resample_mode not in {"nearest", "smooth"}:
        raise ValueError(f"Unsupported resampling mode: {resample_mode}")
    if resample_mode == "nearest":
        return image.convert("RGBA").resize(size, Image.Resampling.NEAREST)

    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    premultiplied = np.rint(rgba[:, :, :3] * alpha).astype(np.uint8)
    packed = np.concatenate((premultiplied, rgba[:, :, 3:4].astype(np.uint8)), axis=2)
    resized = np.asarray(
        Image.fromarray(packed, "RGBA").resize(size, Image.Resampling.LANCZOS),
        dtype=np.float32,
    )

    resized_alpha = resized[:, :, 3:4]
    rgb = np.zeros_like(resized[:, :, :3])
    visible = resized_alpha[:, :, 0] > 0
    rgb[visible] = resized[:, :, :3][visible] * 255.0 / resized_alpha[visible]
    output = np.concatenate((np.clip(np.rint(rgb), 0, 255), resized_alpha), axis=2).astype(np.uint8)
    return Image.fromarray(output, "RGBA")


def transform_premultiplied(
    image: Image.Image,
    size: tuple[int, int],
    affine: tuple[float, float, float, float, float, float],
    resample_mode: str = "smooth",
) -> Image.Image:
    """Apply a Pillow inverse affine transform without introducing alpha-edge halos."""
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("Transform dimensions must be positive.")
    if resample_mode not in {"nearest", "smooth"}:
        raise ValueError(f"Unsupported resampling mode: {resample_mode}")

    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    premultiplied = np.rint(rgba[:, :, :3] * alpha).astype(np.uint8)
    packed = np.concatenate((premultiplied, rgba[:, :, 3:4].astype(np.uint8)), axis=2)
    resample = Image.Resampling.NEAREST if resample_mode == "nearest" else Image.Resampling.BICUBIC
    transformed = np.asarray(
        Image.fromarray(packed, "RGBA").transform(
            size,
            Image.Transform.AFFINE,
            affine,
            resample=resample,
            fillcolor=(0, 0, 0, 0),
        ),
        dtype=np.float32,
    )

    transformed_alpha = transformed[:, :, 3:4]
    rgb = np.zeros_like(transformed[:, :, :3])
    visible = transformed_alpha[:, :, 0] > 0
    rgb[visible] = transformed[:, :, :3][visible] * 255.0 / transformed_alpha[visible]
    output = np.concatenate((np.clip(np.rint(rgb), 0, 255), transformed_alpha), axis=2).astype(np.uint8)
    return Image.fromarray(output, "RGBA")


def dilate_transparent_rgb(image: Image.Image, radius: int = 1) -> Image.Image:
    """Copy nearby visible RGB into transparent pixels without changing alpha."""
    if radius < 0:
        raise ValueError("Dilation radius cannot be negative.")

    pixels = np.array(image.convert("RGBA"), dtype=np.uint8, copy=True)
    if radius == 0:
        return Image.fromarray(pixels, "RGBA")

    height, width = pixels.shape[:2]
    for _ in range(radius):
        source_rgb = pixels[:, :, :3].copy()
        source_alpha = pixels[:, :, 3].copy()
        filled = source_alpha > 0
        transparent = source_alpha == 0

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                source_y0 = max(0, -dy)
                source_y1 = min(height, height - dy)
                source_x0 = max(0, -dx)
                source_x1 = min(width, width - dx)
                target_y0 = max(0, dy)
                target_y1 = min(height, height + dy)
                target_x0 = max(0, dx)
                target_x1 = min(width, width + dx)

                neighbor_visible = source_alpha[source_y0:source_y1, source_x0:source_x1] > 0
                target_transparent = transparent[target_y0:target_y1, target_x0:target_x1]
                fill = target_transparent & neighbor_visible
                if not np.any(fill):
                    continue

                target_rgb = pixels[target_y0:target_y1, target_x0:target_x1, :3]
                neighbor_rgb = source_rgb[source_y0:source_y1, source_x0:source_x1, :3]
                target_rgb[fill] = neighbor_rgb[fill]
                filled[target_y0:target_y1, target_x0:target_x1][fill] = True
                transparent[target_y0:target_y1, target_x0:target_x1][fill] = False

    return Image.fromarray(pixels, "RGBA")

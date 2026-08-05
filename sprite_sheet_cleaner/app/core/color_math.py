from __future__ import annotations

import numpy as np


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert uint8 or float RGB values to CIE Lab using D65 white."""
    values = np.asarray(rgb, dtype=np.float32)
    if values.shape[-1] != 3:
        raise ValueError("RGB input must have a final dimension of three.")
    values = values / 255.0 if values.max(initial=0) > 1.0 else values
    linear = np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        dtype=np.float32,
    )
    xyz = linear @ matrix.T
    xyz /= np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    delta = 6 / 29
    transformed = np.where(xyz > delta**3, np.cbrt(xyz), xyz / (3 * delta**2) + 4 / 29)
    fx, fy, fz = np.moveaxis(transformed, -1, 0)
    return np.stack((116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)), axis=-1)


def lab_distance(rgb: np.ndarray, background_rgb: tuple[int, int, int]) -> np.ndarray:
    pixels_lab = srgb_to_lab(rgb)
    background_lab = srgb_to_lab(np.asarray(background_rgb, dtype=np.float32))
    return np.sqrt(np.sum((pixels_lab - background_lab) ** 2, axis=-1))


def robust_border_color(rgba: np.ndarray, border_width: int = 12) -> tuple[tuple[int, int, int], float]:
    """Estimate a border color and return a confidence in [0, 1]."""
    if rgba.ndim != 3 or rgba.shape[-1] != 4:
        raise ValueError("RGBA input must have shape (height, width, 4).")
    height, width = rgba.shape[:2]
    border = min(border_width, max(1, width // 2), max(1, height // 2))
    mask = np.zeros((height, width), dtype=bool)
    mask[:border, :] = True
    mask[-border:, :] = True
    mask[:, :border] = True
    mask[:, -border:] = True
    samples = rgba[:, :, :3][mask & (rgba[:, :, 3] > 0)]
    if samples.size == 0:
        raise ValueError("No visible border pixels are available.")

    quantized = samples.astype(np.uint16) // 8
    _, inverse, counts = np.unique(quantized, axis=0, return_inverse=True, return_counts=True)
    dominant = samples[inverse == int(np.argmax(counts))]
    center = np.median(dominant, axis=0)
    spread = float(np.median(np.sqrt(np.sum((dominant.astype(np.float32) - center) ** 2, axis=1))))
    confidence = float(np.clip(1.0 - spread / 64.0, 0.0, 1.0))
    return tuple(int(round(channel)) for channel in center), confidence

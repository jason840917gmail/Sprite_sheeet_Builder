from __future__ import annotations

from PIL import Image
import numpy as np


def rgba_array(image: Image.Image) -> np.ndarray:
    """Return an image as a copied uint8 RGBA array."""
    return np.array(image.convert("RGBA"), dtype=np.uint8, copy=True)


def assert_same_rgba(left: Image.Image, right: Image.Image) -> None:
    left_array = rgba_array(left)
    right_array = rgba_array(right)
    if left_array.shape != right_array.shape or not np.array_equal(left_array, right_array):
        raise AssertionError(f"RGBA images differ: {left_array.shape} != {right_array.shape}")


def assert_same_alpha(left: Image.Image, right: Image.Image) -> None:
    left_alpha = rgba_array(left)[:, :, 3]
    right_alpha = rgba_array(right)[:, :, 3]
    if left_alpha.shape != right_alpha.shape or not np.array_equal(left_alpha, right_alpha):
        raise AssertionError("Alpha channels differ")


def hidden_rgb_pixels(image: Image.Image) -> np.ndarray:
    rgba = rgba_array(image)
    return rgba[:, :, :3][rgba[:, :, 3] == 0]

from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.alpha_ops import dilate_transparent_rgb, resize_premultiplied
from sprite_sheet_cleaner.tests.helpers.image_assertions import assert_same_alpha


class AlphaOpsTests(unittest.TestCase):
    def test_dilate_transparent_rgb_preserves_alpha_and_uses_visible_color(self) -> None:
        image = Image.new("RGBA", (3, 3), (220, 10, 220, 0))
        image.putpixel((1, 1), (10, 20, 30, 255))

        result = dilate_transparent_rgb(image, radius=1)

        self.assertEqual(result.getpixel((1, 0)), (10, 20, 30, 0))
        self.assertEqual(result.getpixel((0, 0)), (10, 20, 30, 0))
        self.assertEqual(result.getpixel((1, 1)), (10, 20, 30, 255))
        assert_same_alpha(image, result)

    def test_dilate_zero_radius_returns_same_pixels(self) -> None:
        image = Image.new("RGBA", (2, 2), (1, 2, 3, 0))

        result = dilate_transparent_rgb(image, radius=0)

        self.assertEqual(list(result.getdata()), list(image.getdata()))

    def test_premultiplied_resize_keeps_edge_color(self) -> None:
        image = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
        image.putpixel((0, 0), (255, 0, 0, 255))

        result = resize_premultiplied(image, (8, 1))
        soft_pixels = [result.getpixel((x, 0)) for x in range(result.width) if 0 < result.getpixel((x, 0))[3] < 255]

        self.assertTrue(soft_pixels)
        self.assertTrue(all(pixel[0] >= pixel[1] and pixel[0] >= pixel[2] for pixel in soft_pixels))


if __name__ == "__main__":
    unittest.main()

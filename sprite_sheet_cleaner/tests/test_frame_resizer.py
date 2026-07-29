from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.frame_resizer import resize_frame
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings


class FrameResizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = Image.new("RGBA", (40, 20), (255, 0, 0, 255))

    def test_fit_returns_exact_canvas_with_transparent_padding(self) -> None:
        result = resize_frame(self.image, FrameResizeSettings(64, 64, "fit"))

        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertGreater(result.getchannel("A").getbbox()[2], 0)

    def test_stretch_returns_exact_dimensions(self) -> None:
        result = resize_frame(self.image, FrameResizeSettings(64, 64, "stretch"))

        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.getpixel((32, 32)), (255, 0, 0, 255))

    def test_fill_returns_exact_dimensions_without_transparent_borders(self) -> None:
        result = resize_frame(self.image, FrameResizeSettings(64, 64, "fill"))

        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.getpixel((0, 0))[3], 255)


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.background_detector import detect_background_color


class BackgroundDetectorTests(unittest.TestCase):
    def test_detects_dominant_image_border_color(self) -> None:
        image = Image.new("RGBA", (40, 40), (96, 0, 240, 255))
        for x in range(10, 30):
            for y in range(10, 30):
                image.putpixel((x, y), (20, 120, 30, 255))

        self.assertEqual(detect_background_color(image), (96, 0, 240))

    def test_detects_selection_border_color(self) -> None:
        image = Image.new("RGBA", (80, 80), (10, 10, 10, 255))
        for x in range(20, 60):
            for y in range(20, 60):
                image.putpixel((x, y), (120, 0, 220, 255))
        for x in range(32, 48):
            for y in range(32, 48):
                image.putpixel((x, y), (0, 180, 80, 255))

        self.assertEqual(detect_background_color(image, (20, 20, 40, 40)), (120, 0, 220))


if __name__ == "__main__":
    unittest.main()


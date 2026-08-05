from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.engines.smart_solid import SmartSolidEngine
from sprite_sheet_cleaner.app.models.source_processing_settings import SourceProcessingSettings


class SmartSolidTests(unittest.TestCase):
    def test_smart_solid_removes_border_background_and_protects_enclosed_match(self) -> None:
        image = Image.new("RGBA", (9, 9), (255, 0, 255, 255))
        for x in range(2, 7):
            for y in range(2, 7):
                image.putpixel((x, y), (20, 40, 60, 255))
        image.putpixel((4, 4), (255, 0, 255, 255))
        settings = SourceProcessingSettings(
            background_color=(255, 0, 255),
            transparent_threshold=2,
            foreground_threshold=20,
        )

        result = SmartSolidEngine().remove(image, settings)

        self.assertEqual(int(result.matte[0, 0]), 0)
        self.assertEqual(int(result.matte[4, 4]), 255)
        self.assertEqual(int(result.matte[3, 3]), 255)

    def test_pixel_art_mode_returns_binary_matte(self) -> None:
        image = Image.new("RGBA", (3, 3), (255, 0, 255, 255))
        image.putpixel((1, 1), (240, 10, 240, 255))
        settings = SourceProcessingSettings(pixel_art_mode=True, transparent_threshold=2, foreground_threshold=40)

        result = SmartSolidEngine().remove(image, settings)

        self.assertTrue(set(result.matte.reshape(-1)).issubset({0, 255}))


if __name__ == "__main__":
    unittest.main()

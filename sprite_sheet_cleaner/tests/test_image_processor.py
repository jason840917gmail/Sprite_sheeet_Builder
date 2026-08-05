from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.image_processor import (
    place_on_tile_canvas,
    process_crop,
    remove_background_color,
    trim_transparent_edges,
)
from sprite_sheet_cleaner.app.models.app_settings import AppSettings


class ImageProcessorTests(unittest.TestCase):
    def test_background_removal_makes_matching_pixels_transparent(self) -> None:
        image = Image.new("RGBA", (4, 4), (255, 0, 255, 255))
        image.putpixel((1, 1), (20, 40, 60, 255))

        result = remove_background_color(image, (255, 0, 255), 1)

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((1, 1)), (20, 40, 60, 255))

    def test_trim_transparent_edges_returns_visible_bounds(self) -> None:
        image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        for x in range(3, 7):
            for y in range(2, 6):
                image.putpixel((x, y), (255, 0, 0, 255))

        result = trim_transparent_edges(image)

        self.assertEqual(result.size, (4, 4))

    def test_process_crop_outputs_fixed_tile_canvas(self) -> None:
        source = Image.new("RGBA", (200, 160), (255, 0, 255, 255))
        for x in range(10, 190):
            for y in range(10, 150):
                source.putpixel((x, y), (0, 128, 0, 255))
        settings = AppSettings(tile_width=256, tile_height=256)

        result = process_crop(source, (0, 0, 200, 160), settings)

        self.assertEqual(result.size, (256, 256))
        self.assertGreater(result.getchannel("A").getbbox()[2], 0)

    def test_tile_canvas_preserves_semitransparent_rgba(self) -> None:
        image = Image.new("RGBA", (2, 2), (100, 50, 25, 128))
        settings = AppSettings(tile_width=2, tile_height=2, edge_bleed=0)

        result = place_on_tile_canvas(image, settings)

        self.assertEqual(result.getpixel((0, 0)), (100, 50, 25, 128))


if __name__ == "__main__":
    unittest.main()


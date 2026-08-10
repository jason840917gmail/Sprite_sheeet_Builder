from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.bucket_renderer import prepare_bucket_base
from sprite_sheet_cleaner.app.models.bucket_settings import BucketSettings


class BucketRendererTests(unittest.TestCase):
    def test_fit_normalizes_large_content_to_exact_bucket_size(self) -> None:
        source = Image.new("RGBA", (256, 256), (10, 20, 30, 255))

        result = prepare_bucket_base(
            source,
            BucketSettings(tile_width=64, tile_height=64, resize_mode="fit", edge_bleed=0),
        )

        self.assertEqual(result.size, (64, 64))
        self.assertEqual(result.getpixel((32, 32)), (10, 20, 30, 255))

    def test_fit_preserves_aspect_ratio_with_transparent_padding(self) -> None:
        source = Image.new("RGBA", (8, 4), (200, 50, 25, 255))

        result = prepare_bucket_base(
            source,
            BucketSettings(tile_width=4, tile_height=4, resize_mode="fit", edge_bleed=0),
        )

        self.assertEqual(result.getpixel((2, 0))[3], 0)
        self.assertEqual(result.getpixel((2, 1)), (200, 50, 25, 255))
        self.assertEqual(result.getpixel((2, 3))[3], 0)

    def test_nearest_resampling_preserves_hard_pixel_values(self) -> None:
        source = Image.new("RGBA", (2, 1))
        source.putpixel((0, 0), (255, 0, 0, 255))
        source.putpixel((1, 0), (0, 0, 255, 255))

        result = prepare_bucket_base(
            source,
            BucketSettings(
                tile_width=4,
                tile_height=2,
                resize_mode="stretch",
                resample_mode="nearest",
                edge_bleed=0,
            ),
        )

        self.assertEqual([result.getpixel((x, 0)) for x in range(4)], [
            (255, 0, 0, 255),
            (255, 0, 0, 255),
            (0, 0, 255, 255),
            (0, 0, 255, 255),
        ])

    def test_fill_crops_overflow_to_bucket_canvas(self) -> None:
        source = Image.new("RGBA", (8, 4), (100, 150, 200, 255))

        result = prepare_bucket_base(
            source,
            BucketSettings(tile_width=2, tile_height=4, resize_mode="fill", edge_bleed=0),
        )

        self.assertEqual(result.size, (2, 4))
        self.assertEqual(result.getbbox(), (0, 0, 2, 4))


if __name__ == "__main__":
    unittest.main()

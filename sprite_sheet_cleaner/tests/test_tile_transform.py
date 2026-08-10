from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.tile_transform import (
    angle_between_points,
    render_tile_transform,
    snap_angle,
)
from sprite_sheet_cleaner.app.models.bucket_settings import BucketSettings
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform


class TileTransformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = BucketSettings(tile_width=5, tile_height=5, edge_bleed=0)

    def test_identity_transform_preserves_exact_rgba(self) -> None:
        base = Image.new("RGBA", (5, 5), (12, 34, 56, 0))
        base.putpixel((2, 1), (100, 50, 25, 128))

        result = render_tile_transform(base, self.settings, TileTransform())

        self.assertEqual(result.tobytes(), base.tobytes())

    def test_ninety_degree_rotation_uses_fixed_canvas(self) -> None:
        base = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
        base.putpixel((3, 2), (255, 0, 0, 255))

        result = render_tile_transform(
            base,
            self.settings,
            TileTransform(angle_degrees=90, resample_mode="nearest"),
        )

        self.assertEqual(result.size, (5, 5))
        self.assertEqual(result.getpixel((2, 3)), (255, 0, 0, 255))

    def test_rendering_same_preview_twice_does_not_compound(self) -> None:
        base = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
        base.putpixel((3, 2), (255, 255, 255, 255))
        transform = TileTransform(angle_degrees=27)

        first = render_tile_transform(base, self.settings, transform)
        second = render_tile_transform(base, self.settings, transform)

        self.assertEqual(first.tobytes(), second.tobytes())

    def test_smooth_rotation_preserves_straight_alpha_color(self) -> None:
        base = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
        base.putpixel((3, 2), (240, 0, 0, 128))

        result = render_tile_transform(
            base,
            self.settings,
            TileTransform(angle_degrees=30, resample_mode="smooth"),
        )

        visible = [
            result.getpixel((x, y))
            for y in range(result.height)
            for x in range(result.width)
            if result.getpixel((x, y))[3] > 0
        ]
        self.assertTrue(visible)
        self.assertTrue(all(pixel[0] >= 235 and pixel[1] == 0 and pixel[2] == 0 for pixel in visible))

    def test_angle_helpers_wrap_and_snap(self) -> None:
        self.assertAlmostEqual(angle_between_points((0, 0), (1, 0), (0, 1)), 90.0)
        self.assertEqual(snap_angle(22.0), 15.0)
        self.assertEqual(snap_angle(179.0), 180.0)


if __name__ == "__main__":
    unittest.main()

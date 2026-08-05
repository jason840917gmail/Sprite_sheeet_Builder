from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.retouch import apply_retouch_stroke


class RetouchTests(unittest.TestCase):
    def test_one_pixel_diameter_affects_only_the_center_for_every_mode(self) -> None:
        source = Image.new("RGBA", (5, 5), (10, 20, 30, 255))
        source.putpixel((1, 1), (220, 40, 80, 255))

        erased = apply_retouch_stroke(source, [(2, 2)], mode="erase", diameter=1)
        painted = apply_retouch_stroke(
            source,
            [(2, 2)],
            mode="paint",
            diameter=1,
            color=(200, 100, 50),
        )
        cloned = apply_retouch_stroke(
            source,
            [(2, 2)],
            mode="clone",
            diameter=1,
            color=(220, 40, 80),
        )

        self.assertEqual(erased.getpixel((2, 2))[3], 0)
        self.assertEqual(erased.getpixel((1, 1))[3], 255)
        self.assertEqual(painted.getpixel((2, 2))[:3], (200, 100, 50))
        self.assertEqual(painted.getpixel((1, 1))[:3], (220, 40, 80))
        self.assertEqual(cloned.getpixel((2, 2))[:3], (220, 40, 80))
        self.assertEqual(cloned.getpixel((1, 1))[:3], (220, 40, 80))

    def test_erase_brush_reduces_alpha_without_changing_rgb(self) -> None:
        image = Image.new("RGBA", (5, 5), (10, 20, 30, 255))

        edited = apply_retouch_stroke(image, [(2, 2)], mode="erase", radius=1)

        self.assertEqual(edited.getpixel((2, 2)), (10, 20, 30, 0))
        self.assertEqual(edited.getpixel((0, 0)), (10, 20, 30, 255))

    def test_paint_color_changes_rgb_and_preserves_alpha(self) -> None:
        image = Image.new("RGBA", (5, 5), (10, 20, 30, 128))

        edited = apply_retouch_stroke(
            image,
            [(2, 2)],
            mode="paint",
            radius=1,
            color=(200, 100, 50),
        )

        self.assertEqual(edited.getpixel((2, 2)), (200, 100, 50, 128))

    def test_clone_color_paints_selected_rgb_but_preserves_destination_alpha(self) -> None:
        image = Image.new("RGBA", (6, 2), (0, 0, 0, 255))
        image.putpixel((1, 0), (220, 40, 80, 255))
        image.putpixel((4, 0), (10, 20, 30, 90))

        edited = apply_retouch_stroke(
            image,
            [(4, 0)],
            mode="clone",
            radius=1,
            color=(90, 80, 70),
        )

        self.assertEqual(edited.getpixel((4, 0)), (90, 80, 70, 90))


if __name__ == "__main__":
    unittest.main()

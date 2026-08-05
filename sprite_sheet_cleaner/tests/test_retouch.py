from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.core.retouch import apply_retouch_stroke


class RetouchTests(unittest.TestCase):
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

    def test_clone_color_copies_rgb_but_preserves_destination_alpha(self) -> None:
        image = Image.new("RGBA", (6, 2), (0, 0, 0, 255))
        image.putpixel((1, 0), (220, 40, 80, 255))
        image.putpixel((4, 0), (10, 20, 30, 90))

        edited = apply_retouch_stroke(
            image,
            [(4, 0)],
            mode="clone",
            radius=1,
            clone_origin=(1, 0),
            clone_anchor=(4, 0),
            source_image=image,
        )

        self.assertEqual(edited.getpixel((4, 0)), (220, 40, 80, 90))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import numpy as np

from sprite_sheet_cleaner.app.core.color_math import lab_distance, robust_border_color, srgb_to_lab


class ColorMathTests(unittest.TestCase):
    def test_lab_black_and_white_are_far_apart(self) -> None:
        lab = srgb_to_lab(np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8))

        self.assertAlmostEqual(float(lab[0, 0]), 0.0, places=2)
        self.assertAlmostEqual(float(lab[1, 0]), 100.0, places=2)
        self.assertGreater(float(lab_distance(np.array([[[255, 255, 255]]], dtype=np.uint8), (0, 0, 0))[0, 0]), 90)

    def test_robust_border_color_ignores_small_outlier_group(self) -> None:
        rgba = np.zeros((10, 10, 4), dtype=np.uint8)
        rgba[:, :, :3] = (250, 0, 250)
        rgba[:, :, 3] = 255
        rgba[:2, :2, :3] = (20, 20, 20)

        color, confidence = robust_border_color(rgba, border_width=2)

        self.assertEqual(color, (250, 0, 250))
        self.assertGreater(confidence, 0.8)


if __name__ == "__main__":
    unittest.main()

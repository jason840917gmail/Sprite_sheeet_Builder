from __future__ import annotations

import unittest

import numpy as np

from sprite_sheet_cleaner.app.core.matte_ops import border_connected, soft_threshold


class MatteOpsTests(unittest.TestCase):
    def test_border_connected_does_not_remove_enclosed_candidate(self) -> None:
        mask = np.zeros((7, 7), dtype=bool)
        mask[0, :] = True
        mask[:, 0] = True
        mask[:, -1] = True
        mask[-1, :] = True
        mask[3, 3] = True

        result = border_connected(mask)

        self.assertTrue(result[0, 0])
        self.assertFalse(result[3, 3])

    def test_soft_threshold_has_transparent_soft_and_foreground_bands(self) -> None:
        result = soft_threshold(np.array([0.0, 24.0, 44.0, 64.0, 100.0]), 24, 64)

        self.assertEqual(result.tolist(), [0, 0, 127, 255, 255])


if __name__ == "__main__":
    unittest.main()

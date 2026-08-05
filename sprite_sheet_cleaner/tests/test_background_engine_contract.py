from __future__ import annotations

import unittest

from PIL import Image
import numpy as np

from sprite_sheet_cleaner.app.engines.base import MatteResult


class BackgroundEngineContractTests(unittest.TestCase):
    def test_matte_result_requires_matching_uint8_shape(self) -> None:
        image = Image.new("RGBA", (3, 2))
        result = MatteResult(np.zeros((2, 3), dtype=np.uint8), "test")

        self.assertIs(result.validated(image), result)

    def test_matte_result_rejects_wrong_shape_or_dtype(self) -> None:
        image = Image.new("RGBA", (3, 2))
        with self.assertRaises(ValueError):
            MatteResult(np.zeros((3, 2), dtype=np.uint8), "test").validated(image)
        with self.assertRaises(ValueError):
            MatteResult(np.zeros((2, 3), dtype=np.float32), "test").validated(image)


if __name__ == "__main__":
    unittest.main()

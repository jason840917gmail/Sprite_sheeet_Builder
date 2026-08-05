from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from sprite_sheet_cleaner.app.runtime.paths import owned_leaf


class RuntimePathTests(unittest.TestCase):
    def test_owned_leaf_is_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(owned_leaf(root, "onnx"), (root / "onnx").resolve())

    def test_owned_leaf_rejects_path_separators(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                owned_leaf(Path(directory), "..\\outside")


if __name__ == "__main__":
    unittest.main()

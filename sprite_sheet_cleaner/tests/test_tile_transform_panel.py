from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
    from sprite_sheet_cleaner.app.widgets.tile_transform_panel import TileTransformPanel
except ImportError:
    QApplication = None
    TileTransform = None
    TileTransformPanel = None


@unittest.skipUnless(QApplication is not None and TileTransformPanel is not None, "PySide6 is not installed")
class TileTransformPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_round_trips_transform_values(self) -> None:
        panel = TileTransformPanel()
        transform = TileTransform(
            scale_x=1.25,
            scale_y=0.75,
            angle_degrees=32.5,
            pivot_x=0.25,
            pivot_y=0.8,
            resample_mode="nearest",
        )

        panel.set_transform(transform)
        restored = panel.transform()

        self.assertEqual(restored, transform)

    def test_linked_scale_emits_one_uniform_transform(self) -> None:
        panel = TileTransformPanel()
        emitted = []
        panel.transformChanged.connect(emitted.append)

        panel.scale_x.setValue(150.0)

        self.assertEqual(panel.scale_y.value(), 150.0)
        self.assertEqual(emitted[-1].scale_x, 1.5)
        self.assertEqual(emitted[-1].scale_y, 1.5)


if __name__ == "__main__":
    unittest.main()

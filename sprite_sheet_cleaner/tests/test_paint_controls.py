from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.main_window import MainWindow
    from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage
    from sprite_sheet_cleaner.app.widgets.retouch_panel import RetouchPanel
    from sprite_sheet_cleaner.app.widgets.source_background_panel import SourceBackgroundPanel
except ImportError:
    QApplication = None
    MainWindow = None
    RetouchPanel = None
    SourceBackgroundPanel = None
    pil_to_qimage = None


@unittest.skipUnless(
    QApplication is not None and RetouchPanel is not None and SourceBackgroundPanel is not None,
    "PySide6 is not installed",
)
class PaintControlWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_retouch_sliders_keep_ranges_defaults_and_labels(self) -> None:
        panel = RetouchPanel()

        self.assertEqual((panel.brush_size.minimum(), panel.brush_size.maximum(), panel.brush_size.value()), (1, 512, 24))
        self.assertEqual((panel.opacity.minimum(), panel.opacity.maximum(), panel.opacity.value()), (1, 100, 100))
        self.assertEqual(panel.brush_size.orientation(), Qt.Horizontal)
        self.assertEqual(panel.opacity.orientation(), Qt.Horizontal)
        self.assertEqual(panel.brush_size_value.text(), "24 px")
        self.assertEqual(panel.opacity_value.text(), "100%")

        panel.brush_size.setValue(48)
        panel.opacity.setValue(65)

        self.assertEqual(panel.brush_size_value.text(), "48 px")
        self.assertEqual(panel.opacity_value.text(), "65%")
        self.assertEqual(panel.brush_radius(), 24)
        self.assertEqual(panel.brush_opacity(), 0.65)

    def test_source_background_thresholds_are_horizontal_sliders(self) -> None:
        panel = SourceBackgroundPanel()

        self.assertEqual((panel.tolerance.minimum(), panel.tolerance.maximum(), panel.tolerance.value()), (0, 255, 30))
        self.assertEqual(
            (panel.transparent_threshold.minimum(), panel.transparent_threshold.maximum(), panel.transparent_threshold.value()),
            (0, 255, 24),
        )
        self.assertEqual(
            (panel.foreground_threshold.minimum(), panel.foreground_threshold.maximum(), panel.foreground_threshold.value()),
            (1, 255, 64),
        )
        self.assertEqual(panel.tolerance.orientation(), Qt.Horizontal)
        self.assertEqual(panel.transparent_threshold.orientation(), Qt.Horizontal)
        self.assertEqual(panel.foreground_threshold.orientation(), Qt.Horizontal)

        panel.tolerance.setValue(42)
        panel.transparent_threshold.setValue(12)
        panel.foreground_threshold.setValue(72)

        settings = panel.settings()
        self.assertEqual((settings.tolerance, settings.transparent_threshold, settings.foreground_threshold), (42, 12, 72))
        self.assertEqual((panel.tolerance_value.text(), panel.transparent_threshold_value.text(), panel.foreground_threshold_value.text()), ("42", "12", "72"))


@unittest.skipUnless(QApplication is not None and MainWindow is not None, "PySide6 is not installed")
class PaintBucketTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_bucket_click_in_paint_mode_selects_and_edits_bucket_tile(self) -> None:
        window = MainWindow()
        try:
            source = Image.new("RGBA", (4, 4), (20, 30, 40, 255))
            window.source_image = source
            window.model.add_tile_from_crop(source, (0, 0, 4, 4))
            window.source_viewer.set_image(pil_to_qimage(source))
            window._refresh_all(selected_index=0)
            window._set_viewer_tool("retouch")

            before = window.model.tiles[0].image_rgba.copy()
            window._preview_bucket_tile(0)

            self.assertEqual(window.retouch_panel.current_target(), "bucket")
            self.assertEqual(window._retouch_bucket_index, 0)
            self.assertEqual(window.source_viewer.image_size(), before.size)

            window.retouch_panel.mode.setCurrentIndex(1)
            window.retouch_panel.brush_size.setValue(1)
            window._retouch_pressed((1, 1))
            window._retouch_released()
            self.assertNotEqual(window.model.tiles[0].image_rgba.tobytes(), before.tobytes())

            window._undo_bucket()
            self.assertEqual(window.model.tiles[0].image_rgba.tobytes(), before.tobytes())
            self.assertEqual(window.source_viewer.image_size(), before.size)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

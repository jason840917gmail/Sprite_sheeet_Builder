from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.widgets.source_viewer import SourceViewer
    from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
except ImportError:
    QApplication = None
    SourceViewer = None


@unittest.skipUnless(QApplication is not None and SourceViewer is not None, "PySide6 is not installed")
class SourceViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def make_viewer(self) -> "SourceViewer":
        viewer = SourceViewer()
        viewer.resize(600, 480)
        viewer.set_selection_geometry(10, 10)
        viewer.set_image(QImage(40, 30, QImage.Format_RGBA8888))
        viewer.set_tool("grid")
        viewer.show()
        self.app.processEvents()
        return viewer

    def test_grid_selection_rects_normalize_reverse_drag_in_row_major_order(self) -> None:
        viewer = self.make_viewer()
        try:
            viewer._set_grid_selection_range((3, 2), (1, 0))

            self.assertEqual(
                viewer.selected_grid_rects(),
                [
                    (10, 0, 10, 10),
                    (20, 0, 10, 10),
                    (30, 0, 10, 10),
                    (10, 10, 10, 10),
                    (20, 10, 10, 10),
                    (30, 10, 10, 10),
                    (10, 20, 10, 10),
                    (20, 20, 10, 10),
                    (30, 20, 10, 10),
                ],
            )
        finally:
            viewer.close()

    def test_click_emits_one_cell_while_drag_only_leaves_selection(self) -> None:
        viewer = self.make_viewer()
        clicked: list[tuple[int, int, int, int]] = []
        viewer.gridCellClicked.connect(clicked.append)
        try:
            first = viewer.mapFromScene(QPointF(5, 5))
            third = viewer.mapFromScene(QPointF(25, 5))

            viewer._start_grid_selection(first)
            viewer._finish_grid_selection(first)
            self.assertEqual(clicked, [(0, 0, 10, 10)])

            viewer._start_grid_selection(first)
            viewer._update_grid_selection_drag(third)
            viewer._finish_grid_selection(third)

            self.assertEqual(clicked, [(0, 0, 10, 10)])
            self.assertEqual(viewer.selected_grid_rects(), [(0, 0, 10, 10), (10, 0, 10, 10), (20, 0, 10, 10)])
        finally:
            viewer.close()

    def test_grid_selection_clears_when_grid_origin_moves(self) -> None:
        viewer = SourceViewer()
        viewer.set_selection_geometry(10, 10)
        viewer.set_image(QImage(45, 30, QImage.Format_RGBA8888))
        viewer.set_tool("grid")
        viewer._set_grid_selection_range((0, 0), (1, 1))

        viewer._set_grid_origin((5, 0))

        self.assertEqual(viewer.selected_grid_rects(), [])

    def test_rotate_overlay_only_appears_in_rotate_tool(self) -> None:
        viewer = SourceViewer()
        viewer.set_image(QImage(40, 30, QImage.Format_RGBA8888))
        viewer.set_tile_transform(TileTransform(angle_degrees=15))

        viewer.set_tool("rotate")
        self.assertTrue(viewer._transform_outline_item.isVisible())
        self.assertTrue(all(handle.isVisible() for handle in viewer._transform_handles))

        viewer.set_tool("select")
        self.assertFalse(viewer._transform_outline_item.isVisible())

    def test_rotate_overlay_hit_tests_corner_ring_and_pivot(self) -> None:
        viewer = SourceViewer()
        viewer.set_image(QImage(40, 40, QImage.Format_RGBA8888))
        viewer.set_tool("rotate")
        viewer.set_tile_transform(TileTransform())
        points, pivot = viewer._transform_geometry()

        self.assertEqual(viewer._transform_hit_test(points[0]), "rotate")
        self.assertEqual(viewer._transform_hit_test(pivot), "pivot")
        self.assertEqual(
            viewer._transform_hit_test(QPointF(pivot.x() + 18 / viewer._zoom, pivot.y())),
            "rotate",
        )

    def test_rotate_clipping_warning_uses_visible_content_bounds(self) -> None:
        viewer = SourceViewer()
        viewer.set_image(QImage(40, 40, QImage.Format_RGBA8888))
        viewer.set_tool("rotate")

        viewer.set_tile_transform(TileTransform(angle_degrees=45), (15, 15, 25, 25))

        self.assertEqual(viewer._transform_outline_item.pen().color().name(), "#ffb347")
        self.assertNotIn("clipped", viewer._transform_angle_item.text())

    def test_center_ring_drag_emits_live_rotation_preview(self) -> None:
        viewer = SourceViewer()
        viewer.resize(600, 480)
        viewer.set_image(QImage(100, 100, QImage.Format_RGBA8888))
        viewer.set_tool("rotate")
        viewer.set_tile_transform(TileTransform())
        viewer.show()
        self.app.processEvents()
        emitted = []
        viewer.tileTransformPreviewChanged.connect(emitted.append)
        viewer.tileTransformPreviewChanged.connect(
            lambda transform: viewer.set_tile_transform(transform, preserve_drag=True)
        )
        _points, pivot = viewer._transform_geometry()
        radius = 18 / viewer._zoom
        start = viewer.mapFromScene(QPointF(pivot.x() + radius, pivot.y()))
        middle = viewer.mapFromScene(QPointF(pivot.x() + radius * 0.5, pivot.y() + radius * 0.866))
        end = viewer.mapFromScene(QPointF(pivot.x(), pivot.y() + radius))

        QTest.mousePress(viewer.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(viewer.viewport(), middle)
        QTest.mouseMove(viewer.viewport(), end)
        QTest.mouseRelease(viewer.viewport(), Qt.LeftButton, pos=end)

        self.assertGreaterEqual(len(emitted), 2)
        self.assertAlmostEqual(emitted[-1].angle_degrees, 90.0, delta=2.0)

    def test_rotate_drag_continues_after_preview_feedback(self) -> None:
        viewer = SourceViewer()
        viewer.resize(600, 480)
        viewer.set_image(QImage(100, 100, QImage.Format_RGBA8888))
        viewer.set_tool("rotate")
        viewer.set_tile_transform(TileTransform())
        viewer.show()
        self.app.processEvents()
        emitted = []
        viewer.tileTransformPreviewChanged.connect(emitted.append)
        viewer.tileTransformPreviewChanged.connect(
            lambda transform: viewer.set_tile_transform(transform, preserve_drag=True)
        )
        _points, pivot = viewer._transform_geometry()
        radius = 18 / viewer._zoom
        start = viewer.mapFromScene(QPointF(pivot.x() + radius, pivot.y()))
        middle = viewer.mapFromScene(QPointF(pivot.x() - radius, pivot.y()))
        end = viewer.mapFromScene(QPointF(pivot.x(), pivot.y() - radius))

        QTest.mousePress(viewer.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(viewer.viewport(), middle)
        QTest.mouseMove(viewer.viewport(), end)
        QTest.mouseRelease(viewer.viewport(), Qt.LeftButton, pos=end)

        self.assertGreaterEqual(len(emitted), 2)
        self.assertAlmostEqual(emitted[-1].angle_degrees, -90.0, delta=2.0)

    def test_pivot_drag_continues_after_preview_feedback(self) -> None:
        viewer = SourceViewer()
        viewer.resize(600, 480)
        viewer.set_image(QImage(100, 100, QImage.Format_RGBA8888))
        viewer.set_tool("rotate")
        viewer.set_tile_transform(TileTransform())
        viewer.show()
        self.app.processEvents()
        emitted = []
        viewer.tileTransformPreviewChanged.connect(emitted.append)
        viewer.tileTransformPreviewChanged.connect(
            lambda transform: viewer.set_tile_transform(transform, preserve_drag=True)
        )
        _points, pivot = viewer._transform_geometry()
        start = viewer.mapFromScene(pivot)
        middle = viewer.mapFromScene(QPointF(60, 55))
        end = viewer.mapFromScene(QPointF(70, 65))

        QTest.mousePress(viewer.viewport(), Qt.LeftButton, pos=start)
        QTest.mouseMove(viewer.viewport(), middle)
        QTest.mouseMove(viewer.viewport(), end)
        QTest.mouseRelease(viewer.viewport(), Qt.LeftButton, pos=end)

        self.assertGreaterEqual(len(emitted), 2)
        self.assertAlmostEqual(emitted[-1].pivot_x, 0.7, delta=0.03)
        self.assertAlmostEqual(emitted[-1].pivot_y, 0.65, delta=0.03)


if __name__ == "__main__":
    unittest.main()

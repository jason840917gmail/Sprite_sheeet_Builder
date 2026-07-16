from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.widgets.source_viewer import SourceViewer
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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QImage, QMouseEvent
    from PySide6.QtWidgets import QApplication
    from sprite_sheet_cleaner.app.core.video_source import FrameRef
    from sprite_sheet_cleaner.app.widgets.frame_browser import FrameBrowser
except ImportError:
    QApplication = None
    FrameBrowser = None
    FrameRef = None


@unittest.skipUnless(QApplication is not None and FrameBrowser is not None, "PySide6 is not installed")
class FrameBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_left_and_right_thumbnail_clicks_emit_frame_actions(self) -> None:
        browser = FrameBrowser()
        browser._add_frame(FrameRef(4, 133), QImage(32, 32, QImage.Format_RGBA8888))
        browser._add_frame(FrameRef(8, 267), QImage(32, 32, QImage.Format_RGBA8888))
        browser.list_widget.show()
        browser.list_widget.resize(180, 140)
        self.app.processEvents()

        left_clicked: list[FrameRef] = []
        right_clicked: list[FrameRef] = []
        browser.frameLeftClicked.connect(left_clicked.append)
        browser.frameRightClicked.connect(right_clicked.append)
        item = browser.list_widget.item(0)
        point = browser.list_widget.visualItemRect(item).center()

        left_event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(point),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        browser.list_widget.mousePressEvent(left_event)
        self.assertEqual(left_clicked, [FrameRef(4, 133)])

        second_item = browser.list_widget.item(1)
        second_point = browser.list_widget.visualItemRect(second_item).center()
        second_left_event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(second_point),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        browser.list_widget.mousePressEvent(second_left_event)
        self.assertEqual(left_clicked, [FrameRef(4, 133), FrameRef(8, 267)])
        self.assertEqual(browser.selected_refs(), [FrameRef(4, 133), FrameRef(8, 267)])

        right_event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(point),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        browser.list_widget.mousePressEvent(right_event)
        self.assertEqual(right_clicked, [FrameRef(4, 133)])
        self.assertEqual(browser.selected_refs(), [FrameRef(8, 267)])
        browser.close()


if __name__ == "__main__":
    unittest.main()

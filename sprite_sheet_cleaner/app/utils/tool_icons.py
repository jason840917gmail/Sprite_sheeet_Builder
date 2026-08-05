from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def create_pointer_icon(size: int = 24) -> QIcon:
    return _paint_icon(size, _draw_pointer_icon)


def create_select_icon(size: int = 24) -> QIcon:
    return _paint_icon(size, _draw_select_icon)


def create_grid_icon(size: int = 24) -> QIcon:
    return _paint_icon(size, _draw_grid_icon)


def create_help_icon(size: int = 24) -> QIcon:
    return _paint_icon(size, _draw_help_icon)


def _paint_icon(size: int, draw_callback) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    draw_callback(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def _draw_pointer_icon(painter: QPainter, rect: QRectF) -> None:
    path = QPainterPath()
    path.moveTo(rect.left() + 5.0, rect.top() + 3.0)
    path.lineTo(rect.left() + 5.0, rect.bottom() - 4.0)
    path.lineTo(rect.left() + 10.2, rect.top() + 14.1)
    path.lineTo(rect.left() + 13.0, rect.bottom() - 1.5)
    path.lineTo(rect.left() + 16.2, rect.bottom() - 3.0)
    path.lineTo(rect.left() + 13.3, rect.top() + 11.8)
    path.lineTo(rect.right() - 4.0, rect.top() + 11.8)
    path.closeSubpath()

    painter.setPen(QPen(QColor(14, 22, 32, 220), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(QColor(31, 143, 255, 230))
    painter.drawPath(path)

    painter.setPen(QPen(QColor(240, 248, 255, 220), 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(QPointF(rect.left() + 7.0, rect.top() + 6.0), QPointF(rect.left() + 7.0, rect.top() + 14.2))


def _draw_select_icon(painter: QPainter, rect: QRectF) -> None:
    frame = QRectF(rect.left() + 4.5, rect.top() + 4.5, rect.width() - 9.0, rect.height() - 9.0)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(31, 143, 255, 46))
    painter.drawRoundedRect(frame, 2.5, 2.5)

    dash_pen = QPen(QColor(227, 241, 255, 235), 1.8, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
    dash_pen.setDashPattern([2.2, 2.2])
    painter.setPen(dash_pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(frame, 2.5, 2.5)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(31, 143, 255, 220))
    for x, y in (
        (frame.left() - 1.0, frame.top() - 1.0),
        (frame.right() - 3.0, frame.top() - 1.0),
        (frame.left() - 1.0, frame.bottom() - 3.0),
        (frame.right() - 3.0, frame.bottom() - 3.0),
    ):
        painter.drawRoundedRect(QRectF(x, y, 4.0, 4.0), 1.0, 1.0)


def _draw_grid_icon(painter: QPainter, rect: QRectF) -> None:
    frame = QRectF(rect.left() + 4.0, rect.top() + 4.0, rect.width() - 8.0, rect.height() - 8.0)
    cell_width = frame.width() / 3.0
    cell_height = frame.height() / 3.0

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(70, 220, 150, 80))
    painter.drawRoundedRect(
        QRectF(frame.left() + cell_width, frame.top() + cell_height, cell_width, cell_height),
        1.8,
        1.8,
    )

    outline_pen = QPen(QColor(225, 242, 232, 235), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(outline_pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(frame, 2.5, 2.5)

    painter.setPen(QPen(QColor(70, 220, 150, 220), 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for step in (1, 2):
        x = frame.left() + cell_width * step
        y = frame.top() + cell_height * step
        painter.drawLine(QPointF(x, frame.top()), QPointF(x, frame.bottom()))
        painter.drawLine(QPointF(frame.left(), y), QPointF(frame.right(), y))


def _draw_help_icon(painter: QPainter, rect: QRectF) -> None:
    frame = QRectF(rect.left() + 4.0, rect.top() + 4.0, rect.width() - 8.0, rect.height() - 8.0)
    painter.setPen(QPen(QColor(225, 241, 255, 235), 1.5))
    painter.setBrush(QColor(31, 143, 255, 210))
    painter.drawEllipse(frame)
    painter.setPen(QColor(255, 255, 255, 245))
    painter.drawText(frame, Qt.AlignCenter, "?")

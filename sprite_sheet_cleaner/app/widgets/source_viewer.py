from __future__ import annotations

import math
from typing import Literal

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QWidget,
)

from sprite_sheet_cleaner.app.core.grid_geometry import (
    GridSpec,
    calculate_grid,
    cell_at_point,
    cell_rect,
    clamp_grid_origin,
    rect_cell,
)


ViewerTool = Literal["pointer", "select", "grid"]


class RulerWidget(QWidget):
    def __init__(self, orientation: Literal["horizontal", "vertical"], viewer: "SourceViewer") -> None:
        super().__init__(viewer)
        self._orientation = orientation
        self._viewer = viewer
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(37, 37, 37))
        painter.setPen(QPen(QColor(95, 95, 95), 1))

        if self._orientation == "horizontal":
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        if not self._viewer.has_image():
            return

        painter.setRenderHint(QPainter.TextAntialiasing, True)
        visible_scene = self._viewer.mapToScene(self._viewer.viewport().rect()).boundingRect()
        image_width, image_height = self._viewer.image_size()
        major_step = self._viewer.ruler_step()
        minor_step = self._viewer.ruler_minor_step(major_step)

        if self._orientation == "horizontal":
            self._draw_horizontal_ticks(painter, visible_scene, image_width, major_step, minor_step)
        else:
            self._draw_vertical_ticks(painter, visible_scene, image_height, major_step, minor_step)

    def _draw_horizontal_ticks(
        self,
        painter: QPainter,
        visible_scene: QRectF,
        image_width: int,
        major_step: int,
        minor_step: int,
    ) -> None:
        painter.setPen(QPen(QColor(125, 125, 125), 1))
        for x in self._viewer.tick_values(visible_scene.left(), visible_scene.right(), minor_step, image_width):
            viewport_x = self._viewer.mapFromScene(QPointF(x, 0)).x()
            if viewport_x < 0 or viewport_x > self.width():
                continue
            is_major = x % major_step == 0
            tick_height = 14 if is_major else 7
            painter.drawLine(viewport_x, self.height() - tick_height, viewport_x, self.height())

        painter.setPen(QColor(220, 220, 220))
        for x in self._viewer.tick_values(visible_scene.left(), visible_scene.right(), major_step, image_width):
            viewport_x = self._viewer.mapFromScene(QPointF(x, 0)).x()
            if viewport_x < 0 or viewport_x > self.width():
                continue
            painter.drawText(viewport_x + 4, 2, 72, self.height() - 15, Qt.AlignLeft | Qt.AlignVCenter, str(x))

    def _draw_vertical_ticks(
        self,
        painter: QPainter,
        visible_scene: QRectF,
        image_height: int,
        major_step: int,
        minor_step: int,
    ) -> None:
        painter.setPen(QPen(QColor(125, 125, 125), 1))
        for y in self._viewer.tick_values(visible_scene.top(), visible_scene.bottom(), minor_step, image_height):
            viewport_y = self._viewer.mapFromScene(QPointF(0, y)).y()
            if viewport_y < 0 or viewport_y > self.height():
                continue
            is_major = y % major_step == 0
            tick_width = 14 if is_major else 7
            painter.drawLine(self.width() - tick_width, viewport_y, self.width(), viewport_y)

        painter.setPen(QColor(220, 220, 220))
        for y in self._viewer.tick_values(visible_scene.top(), visible_scene.bottom(), major_step, image_height):
            viewport_y = self._viewer.mapFromScene(QPointF(0, y)).y()
            if viewport_y < 0 or viewport_y > self.height():
                continue
            painter.drawText(2, viewport_y - 8, self.width() - 17, 16, Qt.AlignRight | Qt.AlignVCenter, str(y))


class SourceViewer(QGraphicsView):
    cursorPositionChanged = Signal(int, int)
    selectionChanged = Signal(object)
    zoomChanged = Signal(float)
    toolChanged = Signal(str)
    gridCellClicked = Signal(object)
    gridStatusChanged = Signal(object)

    RULER_HEIGHT = 32
    RULER_WIDTH = 56

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._grid_added_item = QGraphicsPathItem()
        self._grid_item = QGraphicsPathItem()
        self._grid_outline_item = QGraphicsRectItem()
        self._grid_hover_item = QGraphicsRectItem()
        self._selection_item = QGraphicsRectItem()
        self._selection_grid_item = QGraphicsPathItem()

        grid_pen = QPen(QColor(90, 210, 255, 220), 1)
        grid_pen.setCosmetic(True)
        self._grid_item.setPen(grid_pen)
        self._grid_item.setBrush(QBrush(Qt.NoBrush))
        self._grid_item.setVisible(False)

        outline_pen = QPen(QColor(0, 220, 255, 245), 2)
        outline_pen.setCosmetic(True)
        self._grid_outline_item.setPen(outline_pen)
        self._grid_outline_item.setBrush(QBrush(Qt.NoBrush))
        self._grid_outline_item.setVisible(False)

        added_pen = QPen(QColor(70, 220, 150, 190), 1)
        added_pen.setCosmetic(True)
        self._grid_added_item.setPen(added_pen)
        self._grid_added_item.setBrush(QBrush(QColor(70, 220, 150, 46)))
        self._grid_added_item.setVisible(False)

        hover_pen = QPen(QColor("#1f8fff"), 2)
        hover_pen.setCosmetic(True)
        self._grid_hover_item.setPen(hover_pen)
        self._grid_hover_item.setBrush(QBrush(QColor(31, 143, 255, 44)))
        self._grid_hover_item.setVisible(False)

        selection_pen = QPen(QColor("#1f8fff"), 2, Qt.DashLine)
        selection_pen.setCosmetic(True)
        self._selection_item.setPen(selection_pen)
        self._selection_item.setBrush(QBrush(QColor(31, 143, 255, 36)))
        self._selection_item.setVisible(False)

        selection_grid_pen = QPen(QColor("#1f8fff"), 1, Qt.SolidLine)
        selection_grid_pen.setCosmetic(True)
        self._selection_grid_item.setPen(selection_grid_pen)
        self._selection_grid_item.setBrush(QBrush(Qt.NoBrush))
        self._selection_grid_item.setVisible(False)

        self._pixmap_item.setZValue(0)
        self._grid_added_item.setZValue(1)
        self._grid_item.setZValue(2)
        self._grid_outline_item.setZValue(3)
        self._grid_hover_item.setZValue(4)
        self._selection_item.setZValue(5)
        self._selection_grid_item.setZValue(6)

        self._scene.addItem(self._pixmap_item)
        self._scene.addItem(self._grid_added_item)
        self._scene.addItem(self._grid_item)
        self._scene.addItem(self._grid_outline_item)
        self._scene.addItem(self._grid_hover_item)
        self._scene.addItem(self._selection_item)
        self._scene.addItem(self._selection_grid_item)
        self.setScene(self._scene)

        self.setMouseTracking(True)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setViewportMargins(self.RULER_WIDTH, self.RULER_HEIGHT, 0, 0)
        self.setFocusPolicy(Qt.StrongFocus)

        self._image_size = (0, 0)
        self._tool: ViewerTool = "select"
        self._tile_size = (256, 256)
        self._selection_grid_size = (1, 1)
        self._grid_spec: GridSpec | None = None
        self._grid_error: str | None = None
        self._grid_ready_message: str | None = None
        self._grid_origin = (0, 0)
        self._grid_added_rects: set[tuple[int, int, int, int]] = set()
        self._hover_grid_cell: tuple[int, int] | None = None
        self._dragging_grid = False
        self._grid_drag_scene_origin = QPointF()
        self._grid_drag_start_origin = (0, 0)
        self._placing_selection = False
        self._panning = False
        self._pan_origin = QPoint()
        self._pan_h_value = 0
        self._pan_v_value = 0
        self._zoom = 1.0
        self._top_ruler = RulerWidget("horizontal", self)
        self._left_ruler = RulerWidget("vertical", self)
        self._corner_widget = QWidget(self)
        self._corner_widget.setStyleSheet("background-color: #252525; border-right: 1px solid #5f5f5f; border-bottom: 1px solid #5f5f5f;")
        self._tool_hint_label = QLabel(self.viewport())
        self._tool_hint_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._tool_hint_label.setText("")
        self._tool_hint_label.setStyleSheet(
            "background-color: rgba(28, 31, 36, 210);"
            "border: 1px solid rgba(120, 210, 255, 180);"
            "border-radius: 4px;"
            "color: #f2f7ff;"
            "font-size: 12px;"
            "padding: 6px 8px;"
        )
        self._tool_hint_label.hide()
        self._update_cursor()
        self._position_rulers()
        self._position_tool_hint()

    def has_image(self) -> bool:
        return self._image_size != (0, 0)

    def image_size(self) -> tuple[int, int]:
        return self._image_size

    def current_tool(self) -> ViewerTool:
        return self._tool

    def set_tool(self, tool: ViewerTool) -> None:
        if tool not in ("pointer", "select", "grid"):
            raise ValueError(f"Unknown source viewer tool: {tool}")
        self._tool = tool
        if tool != "select" and self._selection_item.isVisible():
            self.clear_selection()
        self._update_cursor()
        self._rebuild_grid()
        self._update_tool_hint()
        self.toolChanged.emit(tool)

    def set_selection_geometry(
        self,
        tile_width: int,
        tile_height: int,
        selection_columns: int = 1,
        selection_rows: int = 1,
    ) -> None:
        self._tile_size = (max(1, int(tile_width)), max(1, int(tile_height)))
        self._selection_grid_size = (max(1, int(selection_columns)), max(1, int(selection_rows)))
        if self._selection_item.isVisible():
            rect = self._fixed_rect_from_top_left(self._selection_item.rect().topLeft())
            self._set_selection_rect(rect)
        self._rebuild_grid()

    def set_fixed_selection_size(self, width: int, height: int) -> None:
        self.set_selection_geometry(width, height, *self._selection_grid_size)

    def set_grid_added_rects(self, rects: list[tuple[int, int, int, int]]) -> None:
        self._grid_added_rects = {tuple(int(value) for value in rect) for rect in rects}
        self._rebuild_added_grid_cells()

    def grid_status_message(self) -> str | None:
        return self._grid_error or self._grid_ready_message

    def grid_cell_for_rect(self, rect: tuple[int, int, int, int]) -> tuple[int, int] | None:
        if self._grid_spec is None:
            return None
        return rect_cell(self._grid_spec, rect, self._grid_origin)

    def grid_origin(self) -> tuple[int, int]:
        return self._grid_origin

    def nudge_selection(self, dx: int, dy: int) -> None:
        if not self._selection_item.isVisible():
            return

        rect = self._selection_item.rect().normalized()
        width = round(rect.width())
        height = round(rect.height())
        if width <= 0 or height <= 0:
            return

        image_width, image_height = self._image_size
        max_x = max(0, image_width - width)
        max_y = max(0, image_height - height)
        x = min(max(round(rect.left()) + int(dx), 0), max_x)
        y = min(max(round(rect.top()) + int(dy), 0), max_y)
        self._set_selection_rect(QRectF(x, y, width, height))

    def nudge_grid(self, dx: int, dy: int) -> None:
        if self._grid_spec is None:
            return
        self._set_grid_origin((self._grid_origin[0] + int(dx), self._grid_origin[1] + int(dy)))

    def set_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        self._pixmap_item.setPixmap(pixmap)
        self._image_size = (pixmap.width(), pixmap.height())
        self._grid_origin = (0, 0)
        self._update_scene_rect()
        self.clear_selection()
        self._rebuild_grid()
        self.reset_zoom()
        self._update_tool_hint()

    def clear_selection(self) -> None:
        self._selection_item.setRect(QRectF())
        self._selection_item.setVisible(False)
        self._selection_grid_item.setPath(QPainterPath())
        self._selection_grid_item.setVisible(False)
        self.selectionChanged.emit(None)

    def selection_rect(self) -> tuple[int, int, int, int] | None:
        if not self._selection_item.isVisible():
            return None
        rect = self._selection_item.rect().normalized()
        width = round(rect.width())
        height = round(rect.height())
        if width <= 0 or height <= 0:
            return None
        return (
            max(0, round(rect.left())),
            max(0, round(rect.top())),
            width,
            height,
        )

    def zoom_in(self) -> None:
        self._zoom_by(1.15)

    def zoom_out(self) -> None:
        self._zoom_by(1 / 1.15)

    def reset_zoom(self) -> None:
        self.resetTransform()
        if self.has_image():
            self.fitInView(self._image_rect().adjusted(-48, -48, 48, 48), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoomChanged.emit(self._zoom)
        self._update_rulers()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_rulers()
        self._position_tool_hint()
        self._update_scene_rect()
        self._update_rulers()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._update_rulers()

    def wheelEvent(self, event) -> None:
        if not self.has_image():
            super().wheelEvent(event)
            return
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def mousePressEvent(self, event) -> None:
        if not self.has_image():
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            if self._tool == "pointer":
                self._start_pan(event)
            elif self._tool == "grid":
                self._click_grid_cell(self._event_pos(event))
            else:
                self._placing_selection = True
                self._place_fixed_selection(self._event_pos(event))
            event.accept()
            return

        if event.button() == Qt.RightButton and self._tool == "grid":
            self._start_grid_drag(event)
            event.accept()
            return

        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._start_pan(event)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.has_image():
            scene_point = self._clamped_scene_point(self._event_pos(event))
            self.cursorPositionChanged.emit(round(scene_point.x()), round(scene_point.y()))

        if self._placing_selection:
            self._place_fixed_selection(self._event_pos(event))
            event.accept()
            return

        if self._dragging_grid:
            self._drag_grid(self._event_pos(event))
            event.accept()
            return

        if self._panning:
            delta = self._event_pos(event) - self._pan_origin
            self.horizontalScrollBar().setValue(self._pan_h_value - delta.x())
            self.verticalScrollBar().setValue(self._pan_v_value - delta.y())
            event.accept()
            return

        if self._tool == "grid":
            self._update_grid_hover(self._event_pos(event))
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._placing_selection:
            self._placing_selection = False
            self.selectionChanged.emit(self.selection_rect())
            event.accept()
            return

        if self._panning and event.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            self._panning = False
            self._update_cursor()
            event.accept()
            return

        if self._dragging_grid and event.button() == Qt.RightButton:
            self._dragging_grid = False
            self._update_cursor()
            self.gridStatusChanged.emit(self.grid_status_message())
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.clear_selection()
            event.accept()
            return
        if event.key() == Qt.Key_A:
            self._pan_view_by_key(-1, 0)
            event.accept()
            return
        if event.key() == Qt.Key_D:
            self._pan_view_by_key(1, 0)
            event.accept()
            return
        if event.key() == Qt.Key_W:
            self._pan_view_by_key(0, -1)
            event.accept()
            return
        if event.key() == Qt.Key_S:
            self._pan_view_by_key(0, 1)
            event.accept()
            return
        if self._tool == "select":
            if event.key() == Qt.Key_Left:
                self.nudge_selection(-1, 0)
                event.accept()
                return
            if event.key() == Qt.Key_Right:
                self.nudge_selection(1, 0)
                event.accept()
                return
            if event.key() == Qt.Key_Up:
                self.nudge_selection(0, -1)
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.nudge_selection(0, 1)
                event.accept()
                return
        if self._tool == "grid":
            if event.key() == Qt.Key_Left:
                self.nudge_grid(-1, 0)
                event.accept()
                return
            if event.key() == Qt.Key_Right:
                self.nudge_grid(1, 0)
                event.accept()
                return
            if event.key() == Qt.Key_Up:
                self.nudge_grid(0, -1)
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.nudge_grid(0, 1)
                event.accept()
                return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_grid_hover_cell(None)
        super().leaveEvent(event)

    def _zoom_by(self, factor: float) -> None:
        self.scale(factor, factor)
        self._zoom *= factor
        self.zoomChanged.emit(self._zoom)
        self._update_rulers()

    def _start_pan(self, event) -> None:
        self._panning = True
        self._pan_origin = self._event_pos(event)
        self._pan_h_value = self.horizontalScrollBar().value()
        self._pan_v_value = self.verticalScrollBar().value()
        self.setCursor(Qt.ClosedHandCursor)

    def _pan_view_by_key(self, dx: int, dy: int) -> None:
        if not self.has_image():
            return
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        step_x = max(visible.width() / 24.0, 1.0)
        step_y = max(visible.height() / 24.0, 1.0)
        if dx:
            bar = self.horizontalScrollBar()
            bar.setValue(int(bar.value() + dx * step_x))
        if dy:
            bar = self.verticalScrollBar()
            bar.setValue(int(bar.value() + dy * step_y))

    def _start_grid_drag(self, event) -> None:
        if self._grid_spec is None:
            self.gridStatusChanged.emit(self._grid_error)
            return
        self._dragging_grid = True
        self._grid_drag_scene_origin = self.mapToScene(self._event_pos(event))
        self._grid_drag_start_origin = self._grid_origin
        self._set_grid_hover_cell(None)
        self.setCursor(Qt.ClosedHandCursor)

    def _drag_grid(self, point: QPoint) -> None:
        if self._grid_spec is None:
            return
        scene_point = self.mapToScene(point)
        delta = scene_point - self._grid_drag_scene_origin
        self._set_grid_origin(
            (
                round(self._grid_drag_start_origin[0] + delta.x()),
                round(self._grid_drag_start_origin[1] + delta.y()),
            )
        )

    def _event_pos(self, event) -> QPoint:
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def _clamped_scene_point(self, point: QPoint) -> QPointF:
        scene_point = self.mapToScene(point)
        width, height = self._image_size
        x = min(max(scene_point.x(), 0), max(width, 0))
        y = min(max(scene_point.y(), 0), max(height, 0))
        return QPointF(x, y)

    def _place_fixed_selection(self, point: QPoint) -> None:
        scene_point = self._clamped_scene_point(point)
        rect = self._fixed_rect_from_top_left(scene_point)
        self._set_selection_rect(rect)

    def _fixed_rect_from_top_left(self, top_left: QPointF) -> QRectF:
        image_width, image_height = self._image_size
        desired_width, desired_height = self._selection_pixel_size()
        selection_width = min(desired_width, max(image_width, 1))
        selection_height = min(desired_height, max(image_height, 1))
        max_x = max(0, image_width - selection_width)
        max_y = max(0, image_height - selection_height)
        x = min(max(round(top_left.x()), 0), max_x)
        y = min(max(round(top_left.y()), 0), max_y)
        return QRectF(x, y, selection_width, selection_height)

    def _selection_pixel_size(self) -> tuple[int, int]:
        tile_width, tile_height = self._tile_size
        columns, rows = self._selection_grid_size
        return tile_width * columns, tile_height * rows

    def _set_selection_rect(self, rect: QRectF) -> None:
        self._selection_item.setRect(rect)
        self._selection_item.setVisible(True)
        self._update_selection_grid()
        self.selectionChanged.emit(self.selection_rect())

    def _update_selection_grid(self) -> None:
        path = QPainterPath()
        if not self._selection_item.isVisible():
            self._selection_grid_item.setPath(path)
            self._selection_grid_item.setVisible(False)
            return

        rect = self._selection_item.rect().normalized()
        tile_width, tile_height = self._tile_size
        columns, rows = self._selection_grid_size

        for column in range(1, columns):
            x = rect.left() + column * tile_width
            if x >= rect.right():
                continue
            path.moveTo(x, rect.top())
            path.lineTo(x, rect.bottom())

        for row in range(1, rows):
            y = rect.top() + row * tile_height
            if y >= rect.bottom():
                continue
            path.moveTo(rect.left(), y)
            path.lineTo(rect.right(), y)

        self._selection_grid_item.setPath(path)
        self._selection_grid_item.setVisible(not path.isEmpty())

    def _update_cursor(self) -> None:
        if self._panning or self._dragging_grid:
            self.setCursor(Qt.ClosedHandCursor)
        elif self._tool == "pointer":
            self.setCursor(Qt.OpenHandCursor)
        elif self._tool == "grid":
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def _rebuild_grid(self) -> None:
        previous_status = self.grid_status_message()
        self._grid_spec = None
        self._grid_error = None
        self._grid_ready_message = None
        self._grid_item.setPath(QPainterPath())
        self._grid_outline_item.setRect(QRectF())
        self._set_grid_hover_cell(None)

        if not self.has_image():
            self._grid_error = "Open a source image before using the Grid tool."
        else:
            try:
                self._grid_spec = calculate_grid(self._image_size, self._tile_size)
            except ValueError as exc:
                self._grid_error = str(exc)

        if self._grid_spec is not None:
            self._grid_origin = clamp_grid_origin(self._grid_spec, self._grid_origin)
            self._grid_item.setPath(self._grid_path(self._grid_spec, self._grid_origin))
            self._grid_outline_item.setRect(
                QRectF(
                    self._grid_origin[0],
                    self._grid_origin[1],
                    self._grid_spec.grid_width,
                    self._grid_spec.grid_height,
                )
            )
            self._grid_ready_message = self._grid_ready_text(self._grid_spec)

        self._grid_item.setVisible(self._tool == "grid" and self._grid_spec is not None)
        self._grid_outline_item.setVisible(self._tool == "grid" and self._grid_spec is not None)
        self._rebuild_added_grid_cells()
        current_status = self._grid_error or self._grid_ready_message
        if previous_status != current_status:
            self.gridStatusChanged.emit(current_status)

    def _set_grid_origin(self, origin: tuple[int, int]) -> None:
        if self._grid_spec is None:
            return
        next_origin = clamp_grid_origin(self._grid_spec, origin)
        if next_origin == self._grid_origin:
            return
        self._grid_origin = next_origin
        self._grid_item.setPath(self._grid_path(self._grid_spec, self._grid_origin))
        self._grid_outline_item.setRect(
            QRectF(
                self._grid_origin[0],
                self._grid_origin[1],
                self._grid_spec.grid_width,
                self._grid_spec.grid_height,
            )
        )
        self._grid_ready_message = self._grid_ready_text(self._grid_spec)
        self._rebuild_added_grid_cells()
        self.gridStatusChanged.emit(self.grid_status_message())

    def _grid_path(self, grid: GridSpec, origin: tuple[int, int]) -> QPainterPath:
        origin_x, origin_y = clamp_grid_origin(grid, origin)
        path = QPainterPath()
        for column in range(grid.columns + 1):
            x = origin_x + column * grid.tile_width
            path.moveTo(x, origin_y)
            path.lineTo(x, origin_y + grid.grid_height)
        for row in range(grid.rows + 1):
            y = origin_y + row * grid.tile_height
            path.moveTo(origin_x, y)
            path.lineTo(origin_x + grid.grid_width, y)
        return path

    def _grid_ready_text(self, grid: GridSpec) -> str:
        message = f"Ready {grid.columns} x {grid.rows}"
        if self._grid_origin != (0, 0):
            message += f" at X {self._grid_origin[0]}, Y {self._grid_origin[1]}"
        leftovers: list[str] = []
        if grid.leftover_width:
            leftovers.append(f"{grid.leftover_width}px right")
        if grid.leftover_height:
            leftovers.append(f"{grid.leftover_height}px bottom")
        if leftovers:
            message += f" (rounded down, leftover {' and '.join(leftovers)})"
        return message

    def _rebuild_added_grid_cells(self) -> None:
        path = QPainterPath()
        if self._grid_spec is not None:
            for rect in sorted(self._grid_added_rects):
                if rect_cell(self._grid_spec, rect, self._grid_origin) is None:
                    continue
                x, y, width, height = rect
                path.addRect(QRectF(x, y, width, height))
        self._grid_added_item.setPath(path)
        self._grid_added_item.setVisible(
            self._tool == "grid" and self._grid_spec is not None and not path.isEmpty()
        )

    def _click_grid_cell(self, point: QPoint) -> None:
        if self._grid_spec is None:
            self.gridStatusChanged.emit(self._grid_error)
            return

        scene_point = self.mapToScene(point)
        cell = cell_at_point(self._grid_spec, (scene_point.x(), scene_point.y()), self._grid_origin)
        if cell is None:
            self._set_grid_hover_cell(None)
            return

        self._set_grid_hover_cell(cell)
        self.gridCellClicked.emit(cell_rect(self._grid_spec, cell[0], cell[1], self._grid_origin))

    def _update_grid_hover(self, point: QPoint) -> None:
        if self._grid_spec is None:
            self._set_grid_hover_cell(None)
            return
        scene_point = self.mapToScene(point)
        self._set_grid_hover_cell(cell_at_point(self._grid_spec, (scene_point.x(), scene_point.y()), self._grid_origin))

    def _set_grid_hover_cell(self, cell: tuple[int, int] | None) -> None:
        self._hover_grid_cell = cell
        if self._grid_spec is None or cell is None or self._tool != "grid":
            self._grid_hover_item.setVisible(False)
            return
        x, y, width, height = cell_rect(self._grid_spec, cell[0], cell[1], self._grid_origin)
        self._grid_hover_item.setRect(QRectF(x, y, width, height))
        self._grid_hover_item.setVisible(True)

    def ruler_step(self) -> int:
        zoom = max(abs(self.transform().m11()), 0.001)
        desired_scene_pixels = max(1, 80 / zoom)
        magnitude = 10 ** math.floor(math.log10(desired_scene_pixels))
        for multiplier in (1, 2, 5, 10):
            step = int(multiplier * magnitude)
            if step >= desired_scene_pixels:
                return max(1, step)
        return max(1, int(10 * magnitude))

    def ruler_minor_step(self, major_step: int) -> int:
        if major_step >= 100:
            return max(1, major_step // 10)
        if major_step >= 10:
            return max(1, major_step // 5)
        return 1

    def tick_values(self, start: float, end: float, step: int, maximum: int) -> list[int]:
        start = max(0, start)
        end = min(maximum, end)
        if end < start:
            return []

        first = int(math.floor(start / step) * step)
        last = int(math.ceil(end / step) * step)
        values = {value for value in range(first, last + step, step) if 0 <= value <= maximum}
        if start <= 0 <= end:
            values.add(0)
        if start <= maximum <= end:
            values.add(maximum)
        return sorted(values)

    def _image_rect(self) -> QRectF:
        return QRectF(0, 0, self._image_size[0], self._image_size[1])

    def _pasteboard_margin(self) -> int:
        image_width, image_height = self._image_size
        return max(image_width, image_height, 512)

    def _update_scene_rect(self) -> None:
        if not self.has_image():
            return
        margin = self._pasteboard_margin()
        image_width, image_height = self._image_size
        self._scene.setSceneRect(
            QRectF(
                -margin,
                -margin,
                image_width + margin * 2,
                image_height + margin * 2,
            )
        )

    def _position_rulers(self) -> None:
        viewport_geometry = self.viewport().geometry()
        ruler_x = viewport_geometry.left()
        ruler_y = viewport_geometry.top()
        self._top_ruler.setGeometry(ruler_x, ruler_y - self.RULER_HEIGHT, viewport_geometry.width(), self.RULER_HEIGHT)
        self._left_ruler.setGeometry(ruler_x - self.RULER_WIDTH, ruler_y, self.RULER_WIDTH, viewport_geometry.height())
        self._corner_widget.setGeometry(
            ruler_x - self.RULER_WIDTH,
            ruler_y - self.RULER_HEIGHT,
            self.RULER_WIDTH,
            self.RULER_HEIGHT,
        )
        self._corner_widget.raise_()
        self._top_ruler.raise_()
        self._left_ruler.raise_()

    def _position_tool_hint(self) -> None:
        if not hasattr(self, "_tool_hint_label"):
            return
        self._tool_hint_label.adjustSize()
        margin = 12
        x = max(margin, self.viewport().width() - self._tool_hint_label.width() - margin)
        self._tool_hint_label.move(x, margin)
        self._tool_hint_label.raise_()

    def _update_tool_hint(self) -> None:
        if not hasattr(self, "_tool_hint_label"):
            return
        hint_text = self._tool_hint_text()
        visible = bool(hint_text and self.has_image())
        if hint_text:
            self._tool_hint_label.setText(hint_text)
        self._tool_hint_label.setVisible(visible)
        if visible:
            self._position_tool_hint()

    def _tool_hint_text(self) -> str | None:
        if self._tool == "select":
            return "Left click: place selection\nArrow keys: nudge 1px\nSpace: add to bucket\nEsc: clear selection\nWASD: pan view"
        if self._tool == "grid":
            return "Left click: add tile\nRight-click drag: move grid\nArrow keys: nudge 1px\nWASD: pan view"
        return None

    def _update_rulers(self) -> None:
        self.viewport().update()
        self._top_ruler.update()
        self._left_ruler.update()
        self._corner_widget.update()

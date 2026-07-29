from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.core.sheet_builder import sheet_capacity, sheet_dimensions
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage


class FinalPreview(QWidget):
    animationRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(240, 180)
        self.animation_button = QPushButton("Open Animation Preview")
        self.animation_button.setEnabled(False)
        self.animation_button.clicked.connect(self.animationRequested.emit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview_label)

        layout = QVBoxLayout(self)
        title = QLabel("Final Tilesheet Preview")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(self.info_label)
        layout.addWidget(self.animation_button, 0, Qt.AlignLeft)
        layout.addWidget(scroll, 1)

    def set_preview(
        self,
        sheet: Image.Image,
        tile_count: int,
        settings: AppSettings,
        tiles: list[TileItem] | None = None,
    ) -> None:
        self._pixmap = QPixmap.fromImage(pil_to_qimage(sheet))
        capacity = sheet_capacity(settings)
        width, height = sheet_dimensions(settings)
        empty_slots = max(0, capacity - tile_count)
        overflow = max(0, tile_count - capacity)
        overflow_text = f" | Overflow: {overflow}" if overflow else ""
        self.info_label.setText(
            f"Tile: {settings.tile_width}x{settings.tile_height} | "
            f"Final tilesheet: {settings.sheet_columns}x{settings.sheet_rows} | "
            f"Output: {width}x{height} | "
            f"Tiles: {tile_count}/{capacity} | "
            f"Empty: {empty_slots}{overflow_text}"
        )
        self.animation_button.setEnabled(bool(tiles))
        self._update_scaled_preview()

    def resizeEvent(self, event) -> None:
        self._update_scaled_preview()
        super().resizeEvent(event)

    def _update_scaled_preview(self) -> None:
        if self._pixmap is None:
            self.preview_label.clear()
            return
        size = self.preview_label.size()
        scaled = self._pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)

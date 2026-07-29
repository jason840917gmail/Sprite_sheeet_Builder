from __future__ import annotations

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage


class _BucketListWidget(QListWidget):
    orderChanged = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        order = [self.item(row).data(Qt.UserRole) for row in range(self.count())]
        self.orderChanged.emit(order)


class BucketPanel(QWidget):
    clearRequested = Signal()
    deleteRequested = Signal(int)
    duplicateRequested = Signal(int)
    moveUpRequested = Signal(int)
    moveDownRequested = Signal(int)
    renameRequested = Signal(int)
    reorderRequested = Signal(object)
    tileClicked = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._capacity: int | None = None
        self.list_widget = _BucketListWidget()
        self.list_widget.setIconSize(QSize(56, 56))
        self.list_widget.setAlternatingRowColors(True)

        self.rename_button = QPushButton("Rename")
        self.duplicate_button = QPushButton("Duplicate")
        self.up_button = QPushButton("Up")
        self.down_button = QPushButton("Down")
        self.delete_button = QPushButton("Delete")
        self.clear_button = QPushButton("Clear Bucket")

        self.up_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.down_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.delete_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        for button in (
            self.rename_button,
            self.duplicate_button,
            self.up_button,
            self.down_button,
            self.delete_button,
            self.clear_button,
        ):
            button_row.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.title_label = QLabel("Bucket 0")
        self.title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(button_row)

        self.rename_button.clicked.connect(lambda: self.renameRequested.emit(self.current_index()))
        self.duplicate_button.clicked.connect(lambda: self.duplicateRequested.emit(self.current_index()))
        self.up_button.clicked.connect(lambda: self.moveUpRequested.emit(self.current_index()))
        self.down_button.clicked.connect(lambda: self.moveDownRequested.emit(self.current_index()))
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.current_index()))
        self.clear_button.clicked.connect(self.clearRequested.emit)
        self.list_widget.orderChanged.connect(self.reorderRequested.emit)
        self.list_widget.itemClicked.connect(
            lambda item: self.tileClicked.emit(self.list_widget.row(item))
        )
        self.list_widget.currentRowChanged.connect(lambda _: self._update_buttons())
        self._update_buttons()

    def current_index(self) -> int:
        return self.list_widget.currentRow()

    def set_tiles(
        self,
        tiles: list[TileItem],
        selected_index: int | None = None,
        capacity: int | None = None,
    ) -> None:
        current = self.current_index() if selected_index is None else selected_index
        self._capacity = capacity
        self.list_widget.clear()

        for index, tile in enumerate(tiles, start=1):
            thumbnail = QPixmap.fromImage(pil_to_qimage(tile.image_rgba)).scaled(
                64,
                64,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            item = QListWidgetItem(QIcon(thumbnail), self._label_for_tile(index, tile))
            item.setData(Qt.UserRole, index - 1)
            self.list_widget.addItem(item)

        if tiles:
            current = min(max(current, 0), len(tiles) - 1)
            self.list_widget.setCurrentRow(current)
        self._update_title()
        self._update_buttons()

    def _label_for_tile(self, index: int, tile: TileItem) -> str:
        return (
            f"{index:03d}_{tile.name}\n"
            f"crop {tile.source_size[0]}x{tile.source_size[1]}  final {tile.final_size[0]}x{tile.final_size[1]}"
        )

    def _update_buttons(self) -> None:
        has_selection = self.current_index() >= 0
        count = self.list_widget.count()
        index = self.current_index()
        has_capacity = self._capacity is None or count < self._capacity
        self.rename_button.setEnabled(has_selection)
        self.duplicate_button.setEnabled(has_selection and has_capacity)
        self.delete_button.setEnabled(has_selection)
        self.clear_button.setEnabled(count > 0)
        self.up_button.setEnabled(has_selection and index > 0)
        self.down_button.setEnabled(has_selection and index < count - 1)

    def _update_title(self) -> None:
        count = self.list_widget.count()
        if self._capacity is None:
            self.title_label.setText(f"Bucket {count}")
            return

        if count > self._capacity:
            overage = count - self._capacity
            self.title_label.setText(f"Bucket {count} / {self._capacity} ({overage} over)")
        elif count == self._capacity:
            self.title_label.setText(f"Bucket {count} / {self._capacity} (full)")
        else:
            remaining = self._capacity - count
            self.title_label.setText(f"Bucket {count} / {self._capacity} ({remaining} empty)")

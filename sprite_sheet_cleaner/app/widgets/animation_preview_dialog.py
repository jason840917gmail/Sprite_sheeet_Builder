from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage


class AnimationPreviewDialog(QDialog):
    def __init__(self, tiles: list[TileItem], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Animation Preview")
        self.setModal(True)
        self.resize(760, 640)
        self._tiles = list(tiles)
        self._index = 0
        self._direction = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

        self.frame_label = QLabel()
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setMinimumSize(520, 420)
        self.frame_label.setStyleSheet("background-color: #252525; border: 1px solid #555;")
        self.counter_label = QLabel()
        self.play_button = QPushButton("Play")
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(1.0, 120.0)
        self.fps_spin.setValue(12.0)
        self.fps_spin.setDecimals(1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Loop (wrap)", "loop")
        self.mode_combo.addItem("Ping-pong", "ping_pong")
        self.mode_combo.setToolTip(
            "Loop (wrap): play the first frame after the last. "
            "Ping-pong: play forward, then backward."
        )
        self.loop_check = QCheckBox("Repeat")
        self.loop_check.setChecked(True)
        self.close_button = QPushButton("Close")

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(QLabel("FPS"))
        controls.addWidget(self.fps_spin)
        controls.addWidget(QLabel("Mode"))
        controls.addWidget(self.mode_combo)
        controls.addWidget(self.loop_check)
        controls.addWidget(self.counter_label, 1)
        controls.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.frame_label, 1)
        layout.addLayout(controls)

        self.play_button.clicked.connect(self._toggle)
        self.fps_spin.valueChanged.connect(self._update_timer)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.close_button.clicked.connect(self.reject)
        self.finished.connect(self._timer.stop)
        self._update_timer()
        self._show_current()

    def _toggle(self) -> None:
        if not self._tiles:
            return
        if self._timer.isActive():
            self._timer.stop()
            self.play_button.setText("Play")
        else:
            self._update_timer()
            self._timer.start()
            self.play_button.setText("Pause")

    def _update_timer(self, _value: float | None = None) -> None:
        self._timer.setInterval(max(1, round(1000 / self.fps_spin.value())))

    def _mode_changed(self, _index: int) -> None:
        self._direction = 1

    def _advance(self) -> None:
        if not self._tiles:
            self._timer.stop()
            self.play_button.setText("Play")
            return

        if not self.loop_check.isChecked() and self._index >= len(self._tiles) - 1:
            self._timer.stop()
            self.play_button.setText("Play")
            self._show_current()
            return

        if self.mode_combo.currentData() == "ping_pong":
            next_index = self._index + self._direction
            if next_index >= len(self._tiles) or next_index < 0:
                self._direction *= -1
                next_index = self._index + self._direction
            self._index = next_index
        else:
            self._index = (self._index + 1) % len(self._tiles)
        self._show_current()

    def _show_current(self) -> None:
        if not self._tiles:
            self.frame_label.clear()
            self.counter_label.setText("0 / 0")
            return
        tile = self._tiles[min(self._index, len(self._tiles) - 1)]
        pixmap = QPixmap.fromImage(pil_to_qimage(tile.image_rgba))
        self.frame_label.setPixmap(
            pixmap.scaled(self.frame_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.counter_label.setText(f"Frame {self._index + 1} / {len(self._tiles)}  {tile.name}")

    def resizeEvent(self, event) -> None:
        self._show_current()
        super().resizeEvent(event)

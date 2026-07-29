from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings


class ResizeFramesDialog(QDialog):
    def __init__(self, parent=None, *, initial_size: tuple[int, int] = (64, 64)) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resize Video Frames")
        self.setModal(True)
        self._updating = False

        self.width_spin = self._spin(initial_size[0])
        self.height_spin = self._spin(initial_size[1])
        self.lock_aspect = QCheckBox("Sym")
        self.lock_aspect.setChecked(True)
        self.mode = QComboBox()
        self.mode.addItem("Fit (preserve aspect, transparent padding)", "fit")
        self.mode.addItem("Stretch (exact dimensions)", "stretch")
        self.mode.addItem("Fill / crop (preserve aspect)", "fill")
        self.set_final_tile_size = QCheckBox("Use target as final tilesheet tile size")
        self.set_final_tile_size.setChecked(True)
        self.help_label = QLabel(
            "The selected frames will be processed at this exact size before they are placed on the final tile canvas."
        )
        self.help_label.setWordWrap(True)

        size_row = QHBoxLayout()
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.setSpacing(6)
        size_row.addWidget(self.width_spin)
        size_row.addWidget(self.lock_aspect)
        size_row.addWidget(self.height_spin)
        size_row.addWidget(QLabel("pixels"))
        size_row.addStretch(1)

        form = QFormLayout()
        form.addRow("Target size", size_row)
        form.addRow("Resize mode", self.mode)
        form.addRow("Output", self.set_final_tile_size)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.help_label)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.width_spin.valueChanged.connect(lambda value: self._sync_dimension("width", value))
        self.height_spin.valueChanged.connect(lambda value: self._sync_dimension("height", value))

    def _spin(self, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 4096)
        spin.setValue(max(1, int(value)))
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setMaximumWidth(96)
        return spin

    def _sync_dimension(self, changed: str, value: int) -> None:
        if self._updating or not self.lock_aspect.isChecked():
            return
        self._updating = True
        if changed == "width":
            self.height_spin.setValue(value)
        else:
            self.width_spin.setValue(value)
        self._updating = False

    def _accept(self) -> None:
        try:
            self.settings()
        except ValueError as exc:
            self.help_label.setText(str(exc))
            return
        self.accept()

    def settings(self) -> FrameResizeSettings:
        return FrameResizeSettings(
            target_width=self.width_spin.value(),
            target_height=self.height_spin.value(),
            mode=self.mode.currentData(),
        ).validated()

    def should_set_final_tile_size(self) -> bool:
        return self.set_final_tile_size.isChecked()

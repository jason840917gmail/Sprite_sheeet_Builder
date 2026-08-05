from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from sprite_sheet_cleaner.app.runtime.registry import RuntimeRegistry


class _InstallSignals(QObject):
    progress = Signal(float)
    finished = Signal(str)
    failed = Signal(str)


class _InstallTask(QRunnable):
    def __init__(self, registry: RuntimeRegistry, runtime_id: str, include_environment: bool, compute: str) -> None:
        super().__init__()
        self.registry = registry
        self.runtime_id = runtime_id
        self.include_environment = include_environment
        self.compute = compute
        self.signals = _InstallSignals()

    def run(self) -> None:
        try:
            manifest = self.registry.get(self.runtime_id)
            self.registry.install_model(manifest, progress=self.signals.progress.emit)
            if self.include_environment:
                self.registry.install_environment(manifest, compute=self.compute)
            self.signals.finished.emit(self.runtime_id)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ModelManagerDialog(QDialog):
    runtimeChanged = Signal()

    def __init__(self, registry: RuntimeRegistry, *, compute: str = "auto", parent=None) -> None:
        super().__init__(parent)
        self.registry = registry
        self.compute = compute
        self.setWindowTitle("Optional AI Model Manager")
        self.resize(620, 420)
        self._pool = QThreadPool(self)
        self._task: _InstallTask | None = None

        self.models = QListWidget()
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.install_model_button = QPushButton("Download model")
        self.install_runtime_button = QPushButton("Download model + runtime")
        self.close_button = QDialogButtonBox(QDialogButtonBox.Close)
        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Auto (CUDA, then CPU)", "auto")
        self.compute_combo.addItem("NVIDIA CUDA only", "cuda")
        self.compute_combo.addItem("CPU only", "cpu")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Optional engines are stored in your user data directory, not the repository."))
        compute_row = QHBoxLayout()
        compute_row.addWidget(QLabel("Runtime backend"))
        compute_row.addWidget(self.compute_combo)
        compute_row.addStretch(1)
        layout.addLayout(compute_row)
        layout.addWidget(self.models)
        layout.addWidget(self.details)
        actions = QHBoxLayout()
        actions.addWidget(self.install_model_button)
        actions.addWidget(self.install_runtime_button)
        actions.addStretch(1)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

        self.models.currentRowChanged.connect(self._selection_changed)
        self.install_model_button.clicked.connect(lambda: self._install(False))
        self.install_runtime_button.clicked.connect(lambda: self._install(True))
        self.close_button.rejected.connect(self.reject)
        self._populate()

    def _populate(self) -> None:
        self.models.clear()
        for manifest in self.registry.manifests():
            self.models.addItem(manifest.display_name)
        if self.models.count():
            self.models.setCurrentRow(0)

    def _selected_manifest(self):
        row = self.models.currentRow()
        manifests = self.registry.manifests()
        return manifests[row] if 0 <= row < len(manifests) else None

    def _selection_changed(self, _row: int) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            self.details.setText("No optional runtimes are registered.")
            return
        state = self.registry.state(manifest)
        metadata = manifest.metadata
        self.details.setText(
            f"{manifest.display_name}\nStatus: {state.message}\n"
            f"Download: {manifest.download_size_bytes / (1024 * 1024):.0f} MiB | "
            f"Installed: {manifest.installed_size_bytes / (1024 * 1024):.0f} MiB\n"
            f"Memory guidance: {metadata.get('memory_guidance', 'not measured')}\n"
            f"License: {manifest.license_name}"
        )
        enabled = self._task is None
        self.install_model_button.setEnabled(enabled)
        self.install_runtime_button.setEnabled(enabled and manifest.supports_current_python())

    def _install(self, include_environment: bool) -> None:
        manifest = self._selected_manifest()
        if manifest is None or self._task is not None:
            return
        self._task = _InstallTask(
            self.registry,
            manifest.runtime_id,
            include_environment,
            str(self.compute_combo.currentData() or self.compute),
        )
        self._task.signals.progress.connect(lambda value: self.details.setText(f"Downloading {round(value * 100)}%"))
        self._task.signals.finished.connect(self._install_finished)
        self._task.signals.failed.connect(self._install_failed)
        self.install_model_button.setEnabled(False)
        self.install_runtime_button.setEnabled(False)
        self._pool.start(self._task)

    def _install_finished(self, runtime_id: str) -> None:
        self._task = None
        self._populate()
        self.runtimeChanged.emit()
        self.details.setText(f"{runtime_id} is installed and verified.")

    def _install_failed(self, message: str) -> None:
        self._task = None
        self.details.setText(f"Installation failed: {message}")
        self._selection_changed(self.models.currentRow())


def default_runtime_registry() -> RuntimeRegistry:
    directory = Path(__file__).resolve().parents[1] / "runtime" / "manifests"
    return RuntimeRegistry.from_directory(directory)

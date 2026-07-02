from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from sprite_sheet_cleaner.app.core.background_detector import detect_background_color
from sprite_sheet_cleaner.app.core.export_manager import export_individual_tiles, export_sheet
from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet, sheet_capacity
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.utils.tool_icons import create_grid_icon, create_pointer_icon, create_select_icon
from sprite_sheet_cleaner.app.utils.qimage_converter import pil_to_qimage
from sprite_sheet_cleaner.app.widgets.bucket_panel import BucketPanel
from sprite_sheet_cleaner.app.widgets.final_preview import FinalPreview
from sprite_sheet_cleaner.app.widgets.settings_panel import SettingsPanel
from sprite_sheet_cleaner.app.widgets.source_viewer import SourceViewer


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sprite Sheet Cleaner")
        self.resize(1320, 820)

        self.model = ProjectModel()
        self.source_image: Image.Image | None = None
        self._last_mouse: tuple[int, int] | None = None
        self._last_selection: tuple[int, int, int, int] | None = None
        self._last_zoom = 1.0

        self.source_viewer = SourceViewer()
        self.settings_panel = SettingsPanel()
        self.bucket_panel = BucketPanel()
        self.final_preview = FinalPreview()
        self._apply_selection_geometry()

        self._build_layout()
        self._create_actions()
        self._connect_signals()
        self._refresh_all()

    def _build_layout(self) -> None:
        self.source_viewer.setMinimumSize(780, 520)
        self.final_preview.setMinimumHeight(170)
        self.settings_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumWidth(310)
        self.bucket_panel.setMinimumHeight(240)

        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.source_viewer)
        self.left_splitter.addWidget(self.final_preview)
        self.left_splitter.setStretchFactor(0, 8)
        self.left_splitter.setStretchFactor(1, 2)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.addWidget(self.settings_panel)
        self.right_splitter.addWidget(self.bucket_panel)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 2)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setStretchFactor(0, 8)
        self.main_splitter.setStretchFactor(1, 2)
        self.setCentralWidget(self.main_splitter)
        QTimer.singleShot(0, self._set_initial_splitter_sizes)

    def _set_initial_splitter_sizes(self) -> None:
        width = max(self.centralWidget().width(), 1)
        height = max(self.centralWidget().height(), 1)
        self.main_splitter.setSizes([round(width * 0.76), round(width * 0.24)])
        self.left_splitter.setSizes([round(height * 0.78), round(height * 0.22)])
        self.right_splitter.setSizes([round(height * 0.36), round(height * 0.64)])

    def _create_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        view_menu = self.menuBar().addMenu("&View")
        tool_menu = self.menuBar().addMenu("&Tools")

        self.tool_bar = QToolBar("Tools", self)
        self.tool_bar.setOrientation(Qt.Vertical)
        self.tool_bar.setMovable(False)
        self.tool_bar.setIconSize(QSize(24, 24))
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.LeftToolBarArea, self.tool_bar)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.pointer_action = QAction(create_pointer_icon(), "Pointer", self)
        self.pointer_action.setCheckable(True)
        self.pointer_action.setShortcut("V")
        self.pointer_action.setToolTip("Pointer: drag the image view")
        self.select_action = QAction(create_select_icon(), "Select", self)
        self.select_action.setCheckable(True)
        self.select_action.setChecked(True)
        self.select_action.setShortcut("S")
        self.select_action.setToolTip("Select: place the fixed-size tile box; arrow keys nudge 1 px")
        self.grid_action = QAction(create_grid_icon(), "Grid", self)
        self.grid_action.setCheckable(True)
        self.grid_action.setShortcut("G")
        self.grid_action.setToolTip("Grid: left-click a tile; right-drag the grid; arrow keys nudge 1 px")
        self.tool_group.addAction(self.pointer_action)
        self.tool_group.addAction(self.select_action)
        self.tool_group.addAction(self.grid_action)
        self.tool_bar.addAction(self.pointer_action)
        self.tool_bar.addAction(self.select_action)
        self.tool_bar.addAction(self.grid_action)
        tool_menu.addAction(self.pointer_action)
        tool_menu.addAction(self.select_action)
        tool_menu.addAction(self.grid_action)

        self.open_action = QAction("&Open Image...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.save_project_action = QAction("&Save Project...", self)
        self.save_project_action.setShortcut(QKeySequence.Save)
        self.load_project_action = QAction("&Load Project...", self)
        self.export_sheet_action = QAction("Export &Sheet...", self)
        self.export_sheet_action.setShortcut("Ctrl+E")
        self.export_tiles_action = QAction("Export Individual &Tiles...", self)
        self.export_tiles_action.setShortcut("Ctrl+Shift+E")
        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)

        for action in (
            self.open_action,
            self.save_project_action,
            self.load_project_action,
            self.export_sheet_action,
            self.export_tiles_action,
        ):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.reset_zoom_action = QAction("&Reset Zoom", self)
        self.reset_zoom_action.setShortcut("Ctrl+0")
        view_menu.addActions((self.zoom_in_action, self.zoom_out_action, self.reset_zoom_action))

        self.add_selection_action = QAction("Add Selection to Bucket", self)
        self.add_selection_action.setShortcut("A")
        self.delete_tile_action = QAction("Delete Tile", self)
        self.delete_tile_action.setShortcut(QKeySequence.Delete)
        self.clear_selection_action = QAction("Clear Source Selection", self)
        self.clear_selection_action.setShortcut("Esc")
        self.addAction(self.add_selection_action)
        self.addAction(self.delete_tile_action)
        self.addAction(self.clear_selection_action)

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(self._open_image)
        self.save_project_action.triggered.connect(self._save_project)
        self.load_project_action.triggered.connect(self._load_project)
        self.export_sheet_action.triggered.connect(self._export_sheet)
        self.export_tiles_action.triggered.connect(self._export_tiles)
        self.exit_action.triggered.connect(self.close)
        self.zoom_in_action.triggered.connect(self.source_viewer.zoom_in)
        self.zoom_out_action.triggered.connect(self.source_viewer.zoom_out)
        self.reset_zoom_action.triggered.connect(self.source_viewer.reset_zoom)
        self.pointer_action.triggered.connect(lambda: self._set_viewer_tool("pointer"))
        self.select_action.triggered.connect(lambda: self._set_viewer_tool("select"))
        self.grid_action.triggered.connect(lambda: self._set_viewer_tool("grid"))
        self.add_selection_action.triggered.connect(self._add_selection_to_bucket)
        self.delete_tile_action.triggered.connect(self._delete_selected_tile)
        self.clear_selection_action.triggered.connect(self._clear_source_selection)

        self.source_viewer.cursorPositionChanged.connect(self._set_mouse_status)
        self.source_viewer.selectionChanged.connect(self._set_selection_status)
        self.source_viewer.zoomChanged.connect(self._set_zoom_status)
        self.source_viewer.toolChanged.connect(lambda _: self._update_status())
        self.source_viewer.gridCellClicked.connect(self._add_grid_cell_to_bucket)
        self.source_viewer.gridStatusChanged.connect(lambda _: self._update_status())
        self.settings_panel.settingsChanged.connect(self._settings_changed)
        self.settings_panel.addSelectionRequested.connect(self._add_selection_to_bucket)
        self.settings_panel.detectBackgroundRequested.connect(self._detect_background_color)
        self.bucket_panel.deleteRequested.connect(self._delete_tile)
        self.bucket_panel.clearRequested.connect(self._clear_bucket)
        self.bucket_panel.duplicateRequested.connect(self._duplicate_tile)
        self.bucket_panel.moveUpRequested.connect(lambda index: self._move_tile(index, -1))
        self.bucket_panel.moveDownRequested.connect(lambda index: self._move_tile(index, 1))
        self.bucket_panel.renameRequested.connect(self._rename_tile)

    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sprite sheet",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)",
        )
        if path:
            self._load_source_image(Path(path), clear_tiles=True)

    def _load_source_image(self, path: Path, *, clear_tiles: bool) -> None:
        try:
            with Image.open(path) as image:
                self.source_image = image.convert("RGBA")
        except Exception as exc:
            QMessageBox.critical(self, "Open image failed", str(exc))
            return

        self.model.source_image_path = str(path)
        if clear_tiles:
            self.model.clear_tiles()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self._last_selection = None
        self._refresh_all()
        detected_color = self._detect_background_color_for_current_image(show_error_dialog=False)
        if detected_color is None:
            self.statusBar().showMessage(f"Opened {path.name}")
            return

        self.statusBar().showMessage(
            f"Opened {path.name} | Auto-detected background #{detected_color[0]:02X}{detected_color[1]:02X}{detected_color[2]:02X}"
        )

    def _save_project(self) -> None:
        if self.source_image is None or not self.model.source_image_path:
            QMessageBox.warning(self, "Save project", "Open a source image before saving a project.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save project",
            "",
            "Sprite Sheet Cleaner project (*.ssc.json);;JSON (*.json)",
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix.lower() != ".json":
            output_path = output_path.with_suffix(".ssc.json")
        try:
            output_path.write_text(json.dumps(self.model.to_project_data(), indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Save project failed", str(exc))
            return
        self.statusBar().showMessage(f"Saved project {output_path.name}")

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load project",
            "",
            "Sprite Sheet Cleaner project (*.ssc.json *.json);;JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        project_path = Path(path)
        try:
            data = json.loads(project_path.read_text(encoding="utf-8"))
            source_path_value = data.get("source_image_path")
            if not source_path_value:
                raise ValueError("Project does not include a source_image_path.")
            source_path = Path(str(source_path_value))
            if not source_path.exists():
                raise FileNotFoundError(f"Source image was not found: {source_path}")
            with Image.open(source_path) as image:
                self.source_image = image.convert("RGBA")
            self.model.load_project_data(data, self.source_image)
        except Exception as exc:
            QMessageBox.critical(self, "Load project failed", str(exc))
            return

        self.settings_panel.set_settings(self.model.settings)
        self._apply_selection_geometry()
        self.source_viewer.set_image(pil_to_qimage(self.source_image))
        self._last_selection = None
        self._refresh_all()
        self.statusBar().showMessage(f"Loaded project {project_path.name}")

    def _settings_changed(self, settings: AppSettings) -> None:
        self.model.settings = settings
        self._apply_selection_geometry()
        if self.source_image is not None and self.model.tiles:
            try:
                self.model.reprocess_tiles(self.source_image)
            except Exception as exc:
                QMessageBox.warning(self, "Settings update failed", str(exc))
        self._refresh_all(selected_index=self.bucket_panel.current_index())

    def _add_selection_to_bucket(self) -> None:
        if self.source_image is None:
            QMessageBox.warning(self, "Add selection", "Open a source image first.")
            return

        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return

        rect = self.source_viewer.selection_rect()
        if rect is None:
            QMessageBox.warning(self, "Add selection", "Use the Select tool to place a tile box first.")
            return

        try:
            tile_rects = self.model.selection_grid_rects(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add selection failed", str(exc))
            return

        available_slots = sheet_capacity(self.model.settings) - len(self.model.tiles)
        if len(tile_rects) > available_slots:
            QMessageBox.warning(
                self,
                "Bucket full",
                f"The selection contains {len(tile_rects)} tiles, but the final tilesheet has "
                f"{available_slots} empty slot(s). Increase rows or columns before adding more.",
            )
            return

        try:
            added_tiles = self.model.add_tiles_from_selection(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add selection failed", str(exc))
            return

        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        if len(added_tiles) == 1:
            self.statusBar().showMessage(f"Added tile {added_tiles[0].name}")
        else:
            self.statusBar().showMessage(f"Added {len(added_tiles)} tiles from selection")

    def _add_grid_cell_to_bucket(self, rect: tuple[int, int, int, int]) -> None:
        if self.source_image is None:
            QMessageBox.warning(self, "Add grid tile", "Open a source image first.")
            return

        existing_index = self._tile_index_for_source_rect(rect)
        if existing_index is not None:
            self._refresh_all(selected_index=existing_index)
            self.statusBar().showMessage("Grid cell is already in the bucket.")
            return

        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return

        try:
            self.model.add_tile_from_crop(self.source_image, rect)
        except Exception as exc:
            QMessageBox.critical(self, "Add grid tile failed", str(exc))
            return

        self._refresh_all(selected_index=len(self.model.tiles) - 1)
        cell = self.source_viewer.grid_cell_for_rect(rect)
        if cell is None:
            self.statusBar().showMessage(f"Added tile {self.model.tiles[-1].name}")
            return
        column, row = cell
        self.statusBar().showMessage(f"Added grid tile row {row + 1}, column {column + 1}")

    def _detect_background_color(self) -> None:
        if self.source_image is None:
            QMessageBox.warning(self, "Detect background", "Open a source image first.")
            return

        color = self._detect_background_color_for_current_image()
        if color is None:
            return
        self.statusBar().showMessage(f"Detected background color #{color[0]:02X}{color[1]:02X}{color[2]:02X}")

    def _detect_background_color_for_current_image(
        self,
        *,
        show_error_dialog: bool = True,
    ) -> tuple[int, int, int] | None:
        if self.source_image is None:
            return None

        try:
            color = detect_background_color(self.source_image, self.source_viewer.selection_rect())
        except Exception as exc:
            if show_error_dialog:
                QMessageBox.critical(self, "Detect background failed", str(exc))
            return None

        self.settings_panel.set_detected_background_color(color)
        return color

    def _export_sheet(self) -> None:
        if not self.model.tiles:
            QMessageBox.warning(self, "Export sheet", "Add at least one tile before exporting.")
            return
        capacity = sheet_capacity(self.model.settings)
        if len(self.model.tiles) > capacity:
            QMessageBox.warning(
                self,
                "Export sheet",
                f"The grid capacity is {capacity}, but the bucket has {len(self.model.tiles)} tiles.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export sheet", "", "PNG image (*.png)")
        if not path:
            return
        try:
            output_path = export_sheet(path, self.model.tiles, self.model.settings)
        except Exception as exc:
            QMessageBox.critical(self, "Export sheet failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported sheet {output_path.name}")

    def _export_tiles(self) -> None:
        if not self.model.tiles:
            QMessageBox.warning(self, "Export tiles", "Add at least one tile before exporting.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Export individual tiles")
        if not folder:
            return
        try:
            paths = export_individual_tiles(folder, self.model.tiles)
        except Exception as exc:
            QMessageBox.critical(self, "Export tiles failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {len(paths)} tiles")

    def _delete_selected_tile(self) -> None:
        self._delete_tile(self.bucket_panel.current_index())

    def _clear_source_selection(self) -> None:
        self.source_viewer.clear_selection()
        self.statusBar().showMessage("Cleared source selection")

    def _delete_tile(self, index: int) -> None:
        if index < 0:
            return
        self.model.remove_tile(index)
        self._refresh_all(selected_index=min(index, len(self.model.tiles) - 1))

    def _clear_bucket(self) -> None:
        count = len(self.model.tiles)
        if count == 0:
            return
        confirmed = (
            QMessageBox.question(
                self,
                "Clear bucket",
                f"Remove all {count} tile(s) from the bucket?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )
        if not confirmed:
            return
        self.model.clear_tiles()
        self._refresh_all()
        self.statusBar().showMessage("Cleared bucket")

    def _duplicate_tile(self, index: int) -> None:
        if index < 0:
            return
        if self._bucket_is_full():
            self._show_bucket_full_warning()
            return
        duplicate = self.model.duplicate_tile(index)
        if duplicate is not None:
            self._refresh_all(selected_index=index + 1)

    def _move_tile(self, index: int, offset: int) -> None:
        if index < 0:
            return
        new_index = self.model.move_tile(index, offset)
        self._refresh_all(selected_index=new_index)

    def _rename_tile(self, index: int) -> None:
        if index < 0:
            return
        current_name = self.model.tiles[index].name
        name, accepted = QInputDialog.getText(self, "Rename tile", "Name", text=current_name)
        if accepted and name.strip():
            self.model.rename_tile(index, name)
            self._refresh_all(selected_index=index)

    def _set_viewer_tool(self, tool: str) -> None:
        self.source_viewer.set_tool(tool)
        self.source_viewer.setFocus(Qt.ShortcutFocusReason)
        if tool == "pointer":
            self.pointer_action.setChecked(True)
        elif tool == "grid":
            self.grid_action.setChecked(True)
            self._warn_if_grid_unavailable()
        else:
            self.select_action.setChecked(True)
        self._update_status()

    def _apply_selection_geometry(self) -> None:
        settings = self.model.settings
        self.source_viewer.set_selection_geometry(
            settings.tile_width,
            settings.tile_height,
            settings.selection_columns,
            settings.selection_rows,
        )

    def _warn_if_grid_unavailable(self) -> None:
        grid_status = self.source_viewer.grid_status_message()
        if self.source_image is not None and grid_status and not grid_status.startswith("Ready"):
            QMessageBox.warning(self, "Grid unavailable", grid_status)

    def _refresh_all(self, selected_index: int | None = None) -> None:
        capacity = sheet_capacity(self.model.settings)
        self.bucket_panel.set_tiles(self.model.tiles, selected_index, capacity)
        self.settings_panel.set_bucket_capacity_state(len(self.model.tiles), capacity)
        self.source_viewer.set_grid_added_rects([tile.source_rect for tile in self.model.tiles])
        sheet = build_sheet(self.model.tiles, self.model.settings, allow_overflow=True)
        self.final_preview.set_preview(sheet, len(self.model.tiles), self.model.settings)
        self._update_status()

    def _bucket_is_full(self) -> bool:
        return len(self.model.tiles) >= sheet_capacity(self.model.settings)

    def _tile_index_for_source_rect(self, rect: tuple[int, int, int, int]) -> int | None:
        normalized = tuple(int(value) for value in rect)
        for index, tile in enumerate(self.model.tiles):
            if tile.source_rect == normalized:
                return index
        return None

    def _show_bucket_full_warning(self) -> None:
        capacity = sheet_capacity(self.model.settings)
        QMessageBox.warning(
            self,
            "Bucket full",
            f"The final tilesheet holds {capacity} tiles. Increase rows or columns before adding more.",
        )

    def _set_mouse_status(self, x: int, y: int) -> None:
        self._last_mouse = (x, y)
        self._update_status()

    def _set_selection_status(self, rect: tuple[int, int, int, int] | None) -> None:
        self._last_selection = rect
        self._update_status()

    def _set_zoom_status(self, zoom: float) -> None:
        self._last_zoom = zoom
        self._update_status()

    def _update_status(self) -> None:
        mouse = (
            f"Mouse: X {self._last_mouse[0]}, Y {self._last_mouse[1]}"
            if self._last_mouse
            else "Mouse: -"
        )
        selection = (
            "Selection: "
            f"X {self._last_selection[0]}, Y {self._last_selection[1]}, "
            f"W {self._last_selection[2]}, H {self._last_selection[3]}"
            if self._last_selection
            else "Selection: -"
        )
        zoom = f"Zoom: {round(self._last_zoom * 100)}%"
        tool = f"Tool: {self.source_viewer.current_tool().title()}"
        grid_status = self.source_viewer.grid_status_message()
        grid = f" | Grid: {grid_status}" if self.source_viewer.current_tool() == "grid" and grid_status else ""
        if self.source_viewer.current_tool() == "grid":
            hint = " | Left click tile; right-drag grid; arrows nudge 1px"
        elif self.source_viewer.current_tool() == "select":
            hint = " | Left click selection; arrows nudge 1px; A add; Esc clear"
        else:
            hint = ""
        self.statusBar().showMessage(f"{tool} | {mouse} | {selection} | {zoom}{grid}{hint}")

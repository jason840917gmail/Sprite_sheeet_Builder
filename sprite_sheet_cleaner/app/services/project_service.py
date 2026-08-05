from __future__ import annotations

from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.storage.project_archive import LoadedProjectArchive, load_project_archive, save_project_archive


def _model_archive_data(model: ProjectModel) -> dict[str, object]:
    data = model.to_project_data()
    data["schema_version"] = 2
    data["tiles"] = [
        {
            "tile_id": tile.tile_id,
            "name": tile.name,
            "source_rect": list(tile.source_rect),
            "source_size": list(tile.source_size),
            "final_size": list(tile.final_size),
            "source_revision_id": tile.source_revision_id,
        }
        for tile in model.tiles
    ]
    return data


def save_model_project(path: str | Path, model: ProjectModel) -> Path:
    data = _model_archive_data(model)
    images = {tile.tile_id: tile.image_rgba for tile in model.tiles}
    return save_project_archive(path, data, images)


def load_model_project(path: str | Path, model: ProjectModel) -> LoadedProjectArchive:
    loaded = load_project_archive(path)
    data = loaded.data
    settings_data = data.get("settings", {})
    if not isinstance(settings_data, dict):
        raise ValueError("Project settings must be an object.")
    settings = AppSettings.from_dict(settings_data)
    tiles_data = data.get("tiles", [])
    if not isinstance(tiles_data, list):
        raise ValueError("Project tiles must be a list.")

    rebuilt: list[TileItem] = []
    for tile_data in tiles_data:
        if not isinstance(tile_data, dict):
            raise ValueError("Each project tile must be an object.")
        tile_id = str(tile_data.get("tile_id") or "")
        if tile_id not in loaded.tile_images:
            raise ValueError(f"Missing tile snapshot: {tile_id}")
        source_rect_data = tile_data.get("source_rect")
        if not isinstance(source_rect_data, (list, tuple)) or len(source_rect_data) != 4:
            raise ValueError("Each project tile needs a source_rect with four values.")
        source_rect = tuple(int(value) for value in source_rect_data)
        source_size_data = tile_data.get("source_size") or source_rect[2:]
        final_size_data = tile_data.get("final_size") or [settings.tile_width, settings.tile_height]
        rebuilt.append(
            TileItem(
                name=str(tile_data.get("name") or f"tile_{len(rebuilt) + 1:03d}"),
                source_rect=source_rect,
                source_size=(int(source_size_data[0]), int(source_size_data[1])),
                final_size=(int(final_size_data[0]), int(final_size_data[1])),
                image_rgba=loaded.tile_images[tile_id],
                tile_id=tile_id,
                source_revision_id=(str(tile_data["source_revision_id"]) if tile_data.get("source_revision_id") else None),
            )
        )
    model.settings = settings
    model.source_image_path = str(data.get("source_image_path")) if data.get("source_image_path") else None
    model.tiles = rebuilt
    return loaded

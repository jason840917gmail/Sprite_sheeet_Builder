from __future__ import annotations

from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.core.project_model import ProjectModel
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
from sprite_sheet_cleaner.app.core.tile_transform import render_tile_transform
from sprite_sheet_cleaner.app.storage.project_archive import LoadedProjectArchive, load_project_archive, save_project_archive


def _model_archive_data(model: ProjectModel) -> dict[str, object]:
    data = model.to_project_data()
    data["schema_version"] = 3
    data["tiles"] = [
        {
            "tile_id": tile.tile_id,
            "name": tile.name,
            "source_rect": list(tile.source_rect),
            "source_size": list(tile.source_size),
            "final_size": list(tile.final_size),
            "source_revision_id": tile.source_revision_id,
            "source_type": tile.source_type,
            "source_frame_index": tile.source_frame_index,
            "source_timestamp_ms": tile.source_timestamp_ms,
            "source_path": tile.source_path,
            "resize_size": list(tile.resize_size) if tile.resize_size is not None else None,
            "resize_mode": tile.resize_mode,
            "transform": tile.transform.to_dict(),
        }
        for tile in model.tiles
    ]
    return data


def save_model_project(path: str | Path, model: ProjectModel) -> Path:
    data = _model_archive_data(model)
    images = {tile.tile_id: tile.base_image_rgba for tile in model.tiles}
    return save_project_archive(path, data, images)


def load_model_project(path: str | Path, model: ProjectModel) -> LoadedProjectArchive:
    loaded = load_project_archive(path)
    data = loaded.data
    settings_data = data.get("settings", {})
    if not isinstance(settings_data, dict):
        raise ValueError("Project settings must be an object.")
    settings = AppSettings.from_dict(settings_data)
    bucket = settings.bucket_settings()
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
        transform = TileTransform.from_dict(tile_data.get("transform"))
        base_image = loaded.tile_images[tile_id]
        if base_image.size != (bucket.tile_width, bucket.tile_height):
            raise ValueError(
                f"Tile base {tile_id} is {base_image.width}x{base_image.height}; "
                f"the project bucket requires {bucket.tile_width}x{bucket.tile_height}."
            )
        rendered = render_tile_transform(base_image, bucket, transform)
        rebuilt.append(
            TileItem(
                name=str(tile_data.get("name") or f"tile_{len(rebuilt) + 1:03d}"),
                source_rect=source_rect,
                source_size=(int(source_size_data[0]), int(source_size_data[1])),
                final_size=rendered.size,
                image_rgba=rendered,
                tile_id=tile_id,
                source_revision_id=(str(tile_data["source_revision_id"]) if tile_data.get("source_revision_id") else None),
                source_type=str(tile_data.get("source_type") or "image"),
                source_frame_index=(
                    int(tile_data["source_frame_index"])
                    if tile_data.get("source_frame_index") is not None
                    else None
                ),
                source_timestamp_ms=(
                    int(tile_data["source_timestamp_ms"])
                    if tile_data.get("source_timestamp_ms") is not None
                    else None
                ),
                source_path=(str(tile_data["source_path"]) if tile_data.get("source_path") else None),
                resize_size=(
                    (int(tile_data["resize_size"][0]), int(tile_data["resize_size"][1]))
                    if isinstance(tile_data.get("resize_size"), (list, tuple))
                    and len(tile_data["resize_size"]) == 2
                    else None
                ),
                resize_mode=(str(tile_data["resize_mode"]) if tile_data.get("resize_mode") else None),
                base_image_rgba=base_image,
                transform=transform,
            )
        )
    model.settings = settings
    model.source_image_path = str(data.get("source_image_path")) if data.get("source_image_path") else None
    model.source_type = str(data.get("source_type") or "image")
    model.video_metadata = data.get("video_metadata") if isinstance(data.get("video_metadata"), dict) else None
    model.video_settings = data.get("video_settings") if isinstance(data.get("video_settings"), dict) else None
    model.tiles = rebuilt
    return loaded

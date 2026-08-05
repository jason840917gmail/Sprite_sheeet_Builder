from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.core.legacy_v1_renderer import render_legacy_tile
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem


def load_legacy_project_into_model(data: dict[str, object], source_image: Image.Image, model) -> None:
    settings_data = data.get("settings", {})
    if not isinstance(settings_data, dict):
        raise ValueError("Project settings must be an object.")
    settings = AppSettings.from_dict(settings_data)
    tiles_data = data.get("tiles", [])
    if not isinstance(tiles_data, list):
        raise ValueError("Project tiles must be a list.")

    rebuilt: list[TileItem] = []
    for index, tile_data in enumerate(tiles_data, start=1):
        if not isinstance(tile_data, dict):
            raise ValueError("Each project tile must be an object.")
        source_rect = tile_data.get("source_rect")
        if not isinstance(source_rect, (list, tuple)) or len(source_rect) != 4:
            raise ValueError("Each project tile needs a source_rect with four values.")
        normalized = tuple(int(value) for value in source_rect)
        image = render_legacy_tile(source_image, normalized, settings)
        rebuilt.append(
            TileItem(
                name=str(tile_data.get("name") or f"tile_{index:03d}"),
                source_rect=normalized,
                source_size=(normalized[2], normalized[3]),
                final_size=(settings.tile_width, settings.tile_height),
                image_rgba=image,
            )
        )
    model.settings = settings
    model.source_image_path = str(data.get("source_image_path")) if data.get("source_image_path") else None
    model.tiles = rebuilt

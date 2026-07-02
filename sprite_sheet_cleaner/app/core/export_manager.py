from __future__ import annotations

from pathlib import Path

from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.file_utils import ensure_png_suffix, safe_filename


def export_sheet(path: str | Path, tiles: list[TileItem], settings: AppSettings) -> Path:
    output_path = ensure_png_suffix(Path(path))
    sheet = build_sheet(tiles, settings)
    sheet.save(output_path, "PNG")
    return output_path


def export_individual_tiles(folder: str | Path, tiles: list[TileItem]) -> list[Path]:
    output_folder = Path(folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for index, tile in enumerate(tiles, start=1):
        filename = f"{index:03d}_{safe_filename(tile.name)}.png"
        output_path = output_folder / filename
        tile.image_rgba.save(output_path, "PNG")
        paths.append(output_path)
    return paths


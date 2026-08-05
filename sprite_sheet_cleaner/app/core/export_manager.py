from __future__ import annotations

from pathlib import Path
import tempfile

from PIL import Image

from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.file_utils import ensure_png_suffix, safe_filename


def export_sheet(path: str | Path, tiles: list[TileItem], settings: AppSettings) -> Path:
    output_path = ensure_png_suffix(Path(path))
    sheet = build_sheet(tiles, settings)
    _validate_png_image(sheet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_save(sheet, output_path)
    return output_path


def export_individual_tiles(folder: str | Path, tiles: list[TileItem]) -> list[Path]:
    output_folder = Path(folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for index, tile in enumerate(tiles, start=1):
        filename = f"{index:03d}_{safe_filename(tile.name)}.png"
        output_path = output_folder / filename
        _validate_png_image(tile.image_rgba)
        _atomic_save(tile.image_rgba, output_path)
        paths.append(output_path)
    return paths


def _validate_png_image(image) -> None:
    if image.mode != "RGBA":
        raise ValueError("Exports must be straight-alpha RGBA PNG images.")
    if image.width <= 0 or image.height <= 0:
        raise ValueError("Export dimensions must be positive.")


def _atomic_save(image, target: Path) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".png", dir=target.parent)
    import os

    os.close(fd)
    temporary = Path(name)
    try:
        image.save(temporary, "PNG")
        with Image.open(temporary) as reopened:
            reopened.load()
            _validate_png_image(reopened)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()


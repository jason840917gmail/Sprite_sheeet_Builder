from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem


def sheet_dimensions(settings: AppSettings) -> tuple[int, int]:
    settings.validated()
    return settings.tile_width * settings.sheet_columns, settings.tile_height * settings.sheet_rows


def sheet_capacity(settings: AppSettings) -> int:
    settings.validated()
    return settings.sheet_columns * settings.sheet_rows


def build_sheet(
    tiles: list[TileItem],
    settings: AppSettings,
    *,
    allow_overflow: bool = False,
) -> Image.Image:
    settings.validated()
    capacity = sheet_capacity(settings)
    if len(tiles) > capacity and not allow_overflow:
        raise ValueError(f"Sheet capacity is {capacity}, but {len(tiles)} tiles were provided.")

    sheet = Image.new("RGBA", sheet_dimensions(settings), (0, 0, 0, 0))
    for index, tile in enumerate(tiles[:capacity]):
        row = index // settings.sheet_columns
        column = index % settings.sheet_columns
        x = column * settings.tile_width
        y = row * settings.tile_height
        image = tile.image_rgba.convert("RGBA")
        sheet.paste(image, (x, y), image)

    return sheet


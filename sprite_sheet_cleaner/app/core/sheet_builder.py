from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem


def sheet_dimensions(settings: AppSettings) -> tuple[int, int]:
    settings.validated()
    return (
        int(settings.bucket_tile_width) * settings.sheet_columns,
        int(settings.bucket_tile_height) * settings.sheet_rows,
    )


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
        bucket_width = int(settings.bucket_tile_width)
        bucket_height = int(settings.bucket_tile_height)
        x = column * bucket_width
        y = row * bucket_height
        image = tile.image_rgba.convert("RGBA")
        if image.size != (bucket_width, bucket_height):
            raise ValueError(
                f"Tile {tile.name!r} is {image.width}x{image.height}; "
                f"the bucket requires {bucket_width}x{bucket_height}."
            )
        sheet.paste(image, (x, y))

    return sheet


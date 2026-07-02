from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, process_crop
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem


CropRect = tuple[int, int, int, int]


def split_selection_grid_rect(
    crop_rect: CropRect,
    tile_width: int,
    tile_height: int,
    columns: int,
    rows: int,
) -> list[CropRect]:
    x, y, width, height = (int(value) for value in crop_rect)
    tile_width = int(tile_width)
    tile_height = int(tile_height)
    columns = int(columns)
    rows = int(rows)

    if width <= 0 or height <= 0:
        raise ValueError("Selection rectangle must have positive width and height.")
    if tile_width <= 0 or tile_height <= 0:
        raise ValueError("Tile dimensions must be positive.")
    if columns <= 0 or rows <= 0:
        raise ValueError("Selection grid dimensions must be positive.")

    rects: list[CropRect] = []
    right = x + width
    bottom = y + height
    for row in range(rows):
        top = y + row * tile_height
        if top >= bottom:
            continue
        cell_height = min(tile_height, bottom - top)
        for column in range(columns):
            left = x + column * tile_width
            if left >= right:
                continue
            cell_width = min(tile_width, right - left)
            rects.append((left, top, cell_width, cell_height))
    return rects


@dataclass
class ProjectModel:
    source_image_path: str | None = None
    settings: AppSettings = field(default_factory=AppSettings)
    tiles: list[TileItem] = field(default_factory=list)

    def clear_tiles(self) -> None:
        self.tiles.clear()

    def next_tile_name(self) -> str:
        return f"tile_{len(self.tiles) + 1:03d}"

    def add_tile_from_crop(
        self,
        source_image: Image.Image,
        crop_rect: CropRect,
        *,
        name: str | None = None,
    ) -> TileItem:
        crop_rect = clamp_crop_rect(source_image, crop_rect)
        image = process_crop(source_image, crop_rect, self.settings)
        item = TileItem(
            name=name or self.next_tile_name(),
            source_rect=crop_rect,
            source_size=(crop_rect[2], crop_rect[3]),
            final_size=(self.settings.tile_width, self.settings.tile_height),
            image_rgba=image,
        )
        self.tiles.append(item)
        return item

    def selection_grid_rects(self, source_image: Image.Image, crop_rect: CropRect) -> list[CropRect]:
        self.settings.validated()
        crop_rect = clamp_crop_rect(source_image, crop_rect)
        return split_selection_grid_rect(
            crop_rect,
            self.settings.tile_width,
            self.settings.tile_height,
            self.settings.selection_columns,
            self.settings.selection_rows,
        )

    def add_tiles_from_selection(self, source_image: Image.Image, crop_rect: CropRect) -> list[TileItem]:
        items: list[TileItem] = []
        for tile_rect in self.selection_grid_rects(source_image, crop_rect):
            items.append(self.add_tile_from_crop(source_image, tile_rect))
        return items

    def remove_tile(self, index: int) -> None:
        if 0 <= index < len(self.tiles):
            del self.tiles[index]

    def duplicate_tile(self, index: int) -> TileItem | None:
        if not 0 <= index < len(self.tiles):
            return None
        duplicate = self.tiles[index].duplicate(f"{self.tiles[index].name}_copy")
        self.tiles.insert(index + 1, duplicate)
        return duplicate

    def move_tile(self, index: int, offset: int) -> int:
        new_index = index + offset
        if not 0 <= index < len(self.tiles) or not 0 <= new_index < len(self.tiles):
            return index
        self.tiles[index], self.tiles[new_index] = self.tiles[new_index], self.tiles[index]
        return new_index

    def rename_tile(self, index: int, name: str) -> None:
        if 0 <= index < len(self.tiles) and name.strip():
            self.tiles[index].name = name.strip()

    def reprocess_tiles(self, source_image: Image.Image) -> None:
        rebuilt: list[TileItem] = []
        for tile in self.tiles:
            crop_rect = clamp_crop_rect(source_image, tile.source_rect)
            rebuilt.append(
                TileItem(
                    name=tile.name,
                    source_rect=crop_rect,
                    source_size=(crop_rect[2], crop_rect[3]),
                    final_size=(self.settings.tile_width, self.settings.tile_height),
                    image_rgba=process_crop(source_image, crop_rect, self.settings),
                )
            )
        self.tiles = rebuilt

    def to_project_data(self) -> dict[str, object]:
        return {
            "source_image_path": self.source_image_path,
            "settings": self.settings.to_dict(),
            "tiles": [
                {
                    "name": tile.name,
                    "source_rect": list(tile.source_rect),
                }
                for tile in self.tiles
            ],
        }

    def load_project_data(self, data: dict[str, object], source_image: Image.Image) -> None:
        self.source_image_path = data.get("source_image_path") or None
        settings_data = data.get("settings", {})
        if not isinstance(settings_data, dict):
            raise ValueError("Project settings must be an object.")
        self.settings = AppSettings.from_dict(settings_data)

        tiles_data = data.get("tiles", [])
        if not isinstance(tiles_data, list):
            raise ValueError("Project tiles must be a list.")

        self.tiles = []
        for tile_data in tiles_data:
            if not isinstance(tile_data, dict):
                raise ValueError("Each project tile must be an object.")
            source_rect = tile_data.get("source_rect")
            if not isinstance(source_rect, (list, tuple)) or len(source_rect) != 4:
                raise ValueError("Each project tile needs a source_rect with four values.")
            name = str(tile_data.get("name") or self.next_tile_name())
            self.add_tile_from_crop(source_image, tuple(int(value) for value in source_rect), name=name)

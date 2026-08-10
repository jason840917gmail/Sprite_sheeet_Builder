from __future__ import annotations

from dataclasses import dataclass

from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.models.app_settings import AppSettings


def clone_tiles(tiles: list[TileItem]) -> list[TileItem]:
    return [
        TileItem(
            name=tile.name,
            source_rect=tile.source_rect,
            source_size=tile.source_size,
            final_size=tile.final_size,
            image_rgba=tile.image_rgba.copy(),
            tile_id=tile.tile_id,
            source_revision_id=tile.source_revision_id,
            source_type=tile.source_type,
            source_frame_index=tile.source_frame_index,
            source_timestamp_ms=tile.source_timestamp_ms,
            source_path=tile.source_path,
            resize_size=tile.resize_size,
            resize_mode=tile.resize_mode,
            base_image_rgba=tile.base_image_rgba.copy(),
            transform=tile.transform.copy(),
        )
        for tile in tiles
    ]


@dataclass(slots=True)
class BucketStateCommand:
    model: object
    before: list[TileItem]
    after: list[TileItem]

    def redo(self) -> None:
        self.model.tiles = clone_tiles(self.after)

    def undo(self) -> None:
        self.model.tiles = clone_tiles(self.before)


def clone_settings(settings: AppSettings) -> AppSettings:
    return AppSettings.from_dict(settings.to_dict())


@dataclass(slots=True)
class BucketResizeCommand:
    model: object
    before_settings: AppSettings
    before_tiles: list[TileItem]
    after_settings: AppSettings
    after_tiles: list[TileItem]

    def redo(self) -> None:
        self.model.settings = clone_settings(self.after_settings)
        self.model.tiles = clone_tiles(self.after_tiles)

    def undo(self) -> None:
        self.model.settings = clone_settings(self.before_settings)
        self.model.tiles = clone_tiles(self.before_tiles)

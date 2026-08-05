from __future__ import annotations

from dataclasses import dataclass

from sprite_sheet_cleaner.app.models.tile_item import TileItem


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

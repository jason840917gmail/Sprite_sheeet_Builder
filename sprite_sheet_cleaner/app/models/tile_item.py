from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(slots=True)
class TileItem:
    name: str
    source_rect: tuple[int, int, int, int]
    source_size: tuple[int, int]
    final_size: tuple[int, int]
    image_rgba: Image.Image

    def duplicate(self, name: str) -> "TileItem":
        return TileItem(
            name=name,
            source_rect=self.source_rect,
            source_size=self.source_size,
            final_size=self.final_size,
            image_rgba=self.image_rgba.copy(),
        )


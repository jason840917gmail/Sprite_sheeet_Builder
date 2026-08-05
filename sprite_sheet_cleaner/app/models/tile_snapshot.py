from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from PIL import Image


@dataclass(slots=True)
class TileSnapshot:
    name: str
    source_rect: tuple[int, int, int, int]
    source_revision_id: str
    source_size: tuple[int, int]
    final_size: tuple[int, int]
    image_rgba: Image.Image
    tile_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        self.image_rgba = self.image_rgba.convert("RGBA").copy()

    def duplicate(self, name: str) -> "TileSnapshot":
        return TileSnapshot(
            name=name,
            source_rect=self.source_rect,
            source_revision_id=self.source_revision_id,
            source_size=self.source_size,
            final_size=self.final_size,
            image_rgba=self.image_rgba.copy(),
        )

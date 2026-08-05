from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from uuid import uuid4

from PIL import Image


@dataclass(slots=True)
class TileItem:
    name: str
    source_rect: tuple[int, int, int, int]
    source_size: tuple[int, int]
    final_size: tuple[int, int]
    image_rgba: Image.Image
    tile_id: str = field(default_factory=lambda: uuid4().hex)
    source_revision_id: str | None = None
    source_type: str = "image"
    source_frame_index: int | None = None
    source_timestamp_ms: int | None = None
    source_path: str | None = None
    resize_size: tuple[int, int] | None = None
    resize_mode: str | None = None

    def duplicate(self, name: str) -> "TileItem":
        return TileItem(
            name=name,
            source_rect=self.source_rect,
            source_size=self.source_size,
            final_size=self.final_size,
            image_rgba=self.image_rgba.copy(),
            source_revision_id=self.source_revision_id,
            source_type=self.source_type,
            source_frame_index=self.source_frame_index,
            source_timestamp_ms=self.source_timestamp_ms,
            source_path=self.source_path,
            resize_size=self.resize_size,
            resize_mode=self.resize_mode,
        )

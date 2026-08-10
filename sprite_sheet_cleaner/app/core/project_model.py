from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

from sprite_sheet_cleaner.app.core.bucket_renderer import prepare_bucket_base
from sprite_sheet_cleaner.app.core.image_processor import (
    clamp_crop_rect,
    process_crop_to_bucket,
    process_crop_with_resize_to_bucket,
)
from sprite_sheet_cleaner.app.core.tile_transform import render_tile_transform
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.frame_resize_settings import FrameResizeSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.models.tile_transform import TileTransform
from sprite_sheet_cleaner.app.core.video_source import FrameRef


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
    source_type: str = "image"
    video_metadata: dict[str, object] | None = None
    video_settings: dict[str, object] | None = None
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
        base, image = process_crop_to_bucket(source_image, crop_rect, self.settings)
        bucket = self.settings.bucket_settings()
        item = TileItem(
            name=name or self.next_tile_name(),
            source_rect=crop_rect,
            source_size=(crop_rect[2], crop_rect[3]),
            final_size=(bucket.tile_width, bucket.tile_height),
            image_rgba=image,
            source_type="image",
            source_path=self.source_image_path,
            base_image_rgba=base,
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
        return self.add_tiles_from_rects(source_image, self.selection_grid_rects(source_image, crop_rect))

    def add_tiles_from_rects(self, source_image: Image.Image, crop_rects: list[CropRect]) -> list[TileItem]:
        items: list[TileItem] = []
        start_index = len(self.tiles)
        for offset, crop_rect in enumerate(crop_rects):
            normalized_rect = clamp_crop_rect(source_image, crop_rect)
            base, image = process_crop_to_bucket(source_image, normalized_rect, self.settings)
            bucket = self.settings.bucket_settings()
            items.append(
                TileItem(
                    name=f"tile_{start_index + offset + 1:03d}",
                    source_rect=normalized_rect,
                    source_size=(normalized_rect[2], normalized_rect[3]),
                    final_size=(bucket.tile_width, bucket.tile_height),
                    image_rgba=image,
                    source_type="image",
                    source_path=self.source_image_path,
                    base_image_rgba=base,
                )
            )
        self.tiles.extend(items)
        return items

    def add_tiles_from_processed_images(
        self,
        source_image: Image.Image,
        processed_images: list[tuple[CropRect, Image.Image]],
    ) -> list[TileItem]:
        """Add final tile images whose background processing is already complete."""
        start_index = len(self.tiles)
        items: list[TileItem] = []
        for offset, (crop_rect, image_rgba) in enumerate(processed_images):
            normalized_rect = clamp_crop_rect(source_image, crop_rect)
            bucket = self.settings.bucket_settings()
            if image_rgba.size == (bucket.tile_width, bucket.tile_height):
                base = image_rgba.convert("RGBA").copy()
            else:
                base = prepare_bucket_base(image_rgba, bucket)
            image = render_tile_transform(base, bucket, TileTransform())
            items.append(
                TileItem(
                    name=f"tile_{start_index + offset + 1:03d}",
                    source_rect=normalized_rect,
                    source_size=(normalized_rect[2], normalized_rect[3]),
                    final_size=(image.width, image.height),
                    image_rgba=image,
                    source_type="image",
                    source_path=self.source_image_path,
                    base_image_rgba=base,
                )
            )
        self.tiles.extend(items)
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

    def resize_bucket_tiles(self, settings: AppSettings) -> None:
        """Atomically move every editable tile base onto a new uniform bucket canvas."""
        settings.validated()
        bucket = settings.bucket_settings()
        resized: list[TileItem] = []
        for tile in self.tiles:
            base = prepare_bucket_base(tile.base_image_rgba, bucket)
            image = render_tile_transform(base, bucket, tile.transform)
            resized.append(
                TileItem(
                    name=tile.name,
                    source_rect=tile.source_rect,
                    source_size=tile.source_size,
                    final_size=image.size,
                    image_rgba=image,
                    tile_id=tile.tile_id,
                    source_revision_id=tile.source_revision_id,
                    source_type=tile.source_type,
                    source_frame_index=tile.source_frame_index,
                    source_timestamp_ms=tile.source_timestamp_ms,
                    source_path=tile.source_path,
                    resize_size=tile.resize_size,
                    resize_mode=tile.resize_mode,
                    base_image_rgba=base,
                    transform=tile.transform.copy(),
                )
            )
        self.settings = settings
        self.tiles = resized

    def reprocess_tiles(self, source_image: Image.Image) -> None:
        rebuilt: list[TileItem] = []
        bucket = self.settings.bucket_settings()
        for tile in self.tiles:
            crop_rect = clamp_crop_rect(source_image, tile.source_rect)
            base, _image = process_crop_to_bucket(source_image, crop_rect, self.settings)
            image = render_tile_transform(base, bucket, tile.transform)
            rebuilt.append(
                TileItem(
                    name=tile.name,
                    source_rect=crop_rect,
                    source_size=(crop_rect[2], crop_rect[3]),
                    final_size=(bucket.tile_width, bucket.tile_height),
                    image_rgba=image,
                    tile_id=tile.tile_id,
                    source_revision_id=tile.source_revision_id,
                    source_type=tile.source_type,
                    source_frame_index=tile.source_frame_index,
                    source_timestamp_ms=tile.source_timestamp_ms,
                    source_path=tile.source_path,
                    resize_size=tile.resize_size,
                    resize_mode=tile.resize_mode,
                    base_image_rgba=base,
                    transform=tile.transform.copy(),
                )
            )
        self.tiles = rebuilt

    def reprocess_video_tiles(
        self,
        frame_provider: Callable[[int], Image.Image],
        source_frame_provider: Callable[[str | None, int], Image.Image] | None = None,
        frame_processor: Callable[[Image.Image, TileItem], Image.Image] | None = None,
    ) -> None:
        rebuilt: list[TileItem] = []
        bucket = self.settings.bucket_settings()
        for tile in self.tiles:
            if tile.source_type != "video" or tile.source_frame_index is None:
                rebuilt.append(tile)
                continue
            if source_frame_provider is not None:
                frame = source_frame_provider(tile.source_path, tile.source_frame_index)
            else:
                frame = frame_provider(tile.source_frame_index)
            if frame_processor is not None:
                frame = frame_processor(frame, tile)
            crop_rect = clamp_crop_rect(frame, tile.source_rect)
            resize_settings = None
            if tile.resize_size is not None and tile.resize_mode is not None:
                resize_settings = FrameResizeSettings(*tile.resize_size, mode=tile.resize_mode).validated()
            base, _image = process_crop_with_resize_to_bucket(frame, crop_rect, self.settings, resize_settings)
            image = render_tile_transform(base, bucket, tile.transform)
            rebuilt.append(
                TileItem(
                    name=tile.name,
                    source_rect=crop_rect,
                    source_size=(crop_rect[2], crop_rect[3]),
                    final_size=(bucket.tile_width, bucket.tile_height),
                    image_rgba=image,
                    tile_id=tile.tile_id,
                    source_revision_id=tile.source_revision_id,
                    source_type="video",
                    source_frame_index=tile.source_frame_index,
                    source_timestamp_ms=tile.source_timestamp_ms,
                    source_path=tile.source_path,
                    resize_size=tile.resize_size,
                    resize_mode=tile.resize_mode,
                    base_image_rgba=base,
                    transform=tile.transform.copy(),
                )
            )
        self.tiles = rebuilt

    def add_video_frames(
        self,
        frames: list[tuple[FrameRef, Image.Image]],
        *,
        crop_rect: CropRect | None = None,
        source_path: str | None = None,
        resize_settings_by_frame: dict[int, FrameResizeSettings] | None = None,
    ) -> list[TileItem]:
        if not frames:
            return []
        existing_indices = {
            (tile.source_path, tile.source_frame_index)
            for tile in self.tiles
            if tile.source_type == "video"
            and tile.source_frame_index is not None
        }
        pending: list[TileItem] = []
        bucket = self.settings.bucket_settings()
        for ref, frame in sorted(frames, key=lambda pair: pair[0].index):
            frame_key = (source_path, ref.index)
            if frame_key in existing_indices:
                continue
            rect = crop_rect or (0, 0, frame.width, frame.height)
            normalized_rect = clamp_crop_rect(frame, rect)
            resize_settings = (resize_settings_by_frame or {}).get(ref.index)
            if resize_settings is not None:
                resize_settings.validated()
            base, image = process_crop_with_resize_to_bucket(frame, normalized_rect, self.settings, resize_settings)
            pending.append(
                TileItem(
                    name=f"frame_{ref.index:04d}",
                    source_rect=normalized_rect,
                    source_size=(normalized_rect[2], normalized_rect[3]),
                    final_size=(bucket.tile_width, bucket.tile_height),
                    image_rgba=image,
                    source_type="video",
                    source_frame_index=ref.index,
                    source_timestamp_ms=ref.timestamp_ms,
                    source_path=source_path,
                    resize_size=(resize_settings.target_width, resize_settings.target_height)
                    if resize_settings is not None
                    else None,
                    resize_mode=resize_settings.mode if resize_settings is not None else None,
                    base_image_rgba=base,
                )
            )
            existing_indices.add(frame_key)
        self.tiles.extend(pending)
        return pending

    def to_project_data(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "source_type": self.source_type,
            "source_image_path": self.source_image_path,
            "video_metadata": self.video_metadata,
            "video_settings": self.video_settings,
            "settings": self.settings.to_dict(),
            "tiles": [
                {
                    "tile_id": tile.tile_id,
                    "name": tile.name,
                    "source_rect": list(tile.source_rect),
                    "source_revision_id": tile.source_revision_id,
                    "source_type": tile.source_type,
                    "source_frame_index": tile.source_frame_index,
                    "source_timestamp_ms": tile.source_timestamp_ms,
                    "source_path": tile.source_path,
                    "resize_size": list(tile.resize_size) if tile.resize_size is not None else None,
                    "resize_mode": tile.resize_mode,
                    "transform": tile.transform.to_dict(),
                }
                for tile in self.tiles
            ],
        }

    def load_project_data(self, data: dict[str, object], source_image: Image.Image) -> None:
        self.source_image_path = data.get("source_image_path") or None
        self.source_type = str(data.get("source_type") or "image")
        self.video_metadata = data.get("video_metadata") if isinstance(data.get("video_metadata"), dict) else None
        self.video_settings = data.get("video_settings") if isinstance(data.get("video_settings"), dict) else None
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
            item = self.add_tile_from_crop(source_image, tuple(int(value) for value in source_rect), name=name)
            if tile_data.get("tile_id"):
                item.tile_id = str(tile_data["tile_id"])
            if tile_data.get("source_revision_id"):
                item.source_revision_id = str(tile_data["source_revision_id"])
            item.source_type = str(tile_data.get("source_type") or "image")
            frame_index = tile_data.get("source_frame_index")
            item.source_frame_index = int(frame_index) if frame_index is not None else None
            timestamp = tile_data.get("source_timestamp_ms")
            item.source_timestamp_ms = int(timestamp) if timestamp is not None else None
            item.source_path = str(tile_data.get("source_path")) if tile_data.get("source_path") else None
            resize_size = tile_data.get("resize_size")
            if isinstance(resize_size, (list, tuple)) and len(resize_size) == 2:
                item.resize_size = (int(resize_size[0]), int(resize_size[1]))
            item.resize_mode = str(tile_data.get("resize_mode")) if tile_data.get("resize_mode") else None
            item.transform = TileTransform.from_dict(tile_data.get("transform"))
            item.image_rgba = render_tile_transform(
                item.base_image_rgba,
                self.settings.bucket_settings(),
                item.transform,
            )
            item.final_size = item.image_rgba.size

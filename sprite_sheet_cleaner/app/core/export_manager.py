from __future__ import annotations

from pathlib import Path
import json

from sprite_sheet_cleaner.app.core.sheet_builder import build_sheet
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.tile_item import TileItem
from sprite_sheet_cleaner.app.utils.file_utils import ensure_png_suffix, safe_filename


def export_sheet(path: str | Path, tiles: list[TileItem], settings: AppSettings) -> Path:
    output_path = ensure_png_suffix(Path(path))
    sheet = build_sheet(tiles, settings)
    sheet.save(output_path, "PNG")
    return output_path


def export_individual_tiles(folder: str | Path, tiles: list[TileItem]) -> list[Path]:
    output_folder = Path(folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for index, tile in enumerate(tiles, start=1):
        suffix = ""
        if tile.source_type == "video" and tile.source_frame_index is not None:
            timestamp = tile.source_timestamp_ms if tile.source_timestamp_ms is not None else 0
            suffix = f"_f{tile.source_frame_index:04d}_t{timestamp:06d}ms"
        filename = f"{index:03d}_{safe_filename(tile.name)}{suffix}.png"
        output_path = output_folder / filename
        tile.image_rgba.save(output_path, "PNG")
        paths.append(output_path)
    return paths


def export_metadata(
    path: str | Path,
    tiles: list[TileItem],
    settings: AppSettings,
    *,
    source_path: str | None = None,
    video_metadata: dict[str, object] | None = None,
    animation_fps: float | None = None,
    video_sources: list[dict[str, object]] | None = None,
) -> Path:
    """Write engine-friendly source and sheet coordinates beside an export."""
    output_path = Path(path)
    if output_path.suffix.lower() != ".json":
        output_path = output_path.with_suffix(".json")

    settings.validated()
    frames: list[dict[str, object]] = []
    for index, tile in enumerate(tiles):
        row = index // settings.sheet_columns
        column = index % settings.sheet_columns
        frames.append(
            {
                "index": index,
                "name": tile.name,
                "sheet_rect": [
                    column * settings.tile_width,
                    row * settings.tile_height,
                    settings.tile_width,
                    settings.tile_height,
                ],
                "source_rect": list(tile.source_rect),
                "source_type": tile.source_type,
                "source_path": tile.source_path,
                "source_frame_index": tile.source_frame_index,
                "source_timestamp_ms": tile.source_timestamp_ms,
                "resize_size": list(tile.resize_size) if tile.resize_size is not None else None,
                "resize_mode": tile.resize_mode,
            }
        )

    payload = {
        "schema_version": 1,
        "source_path": source_path,
        "video_metadata": video_metadata,
        "video_sources": video_sources,
        "animation_fps": animation_fps,
        "sheet": {
            "tile_width": settings.tile_width,
            "tile_height": settings.tile_height,
            "columns": settings.sheet_columns,
            "rows": settings.sheet_rows,
        },
        "frames": frames,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path

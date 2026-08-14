from __future__ import annotations

from copy import deepcopy
from pathlib import Path


def migrate_project_data(data: dict[str, object]) -> dict[str, object]:
    migrated = deepcopy(data)
    version = int(migrated.get("schema_version", 2))
    if version == 4:
        return migrated
    if version == 3 and "sources" not in migrated:
        return migrated
    if version not in {2, 3}:
        raise ValueError(f"Unsupported project schema: {version}")

    settings = migrated.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Project settings must be an object.")
    settings = dict(settings)
    tile_width = int(settings.get("tile_width", 256))
    tile_height = int(settings.get("tile_height", 256))
    legacy_scale = str(settings.get("scale_mode", "none"))
    settings.setdefault("bucket_tile_width", tile_width)
    settings.setdefault("bucket_tile_height", tile_height)
    settings.setdefault("lock_bucket_aspect", bool(settings.get("lock_tile_aspect", True)))
    settings.setdefault(
        "bucket_resize_mode",
        {
            "none": "none",
            "scale_down_only": "fit_down_only",
            "scale_to_fit": "fit",
        }.get(legacy_scale, "none"),
    )
    settings.setdefault("bucket_resample_mode", "smooth")
    migrated["settings"] = settings

    tiles = migrated.get("tiles", [])
    if not isinstance(tiles, list):
        raise ValueError("Project tiles must be a list.")
    normalized_tiles: list[object] = []
    for tile in tiles:
        if not isinstance(tile, dict):
            normalized_tiles.append(tile)
            continue
        normalized = dict(tile)
        normalized.setdefault(
            "transform",
            {
                "version": 1,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "angle_degrees": 0.0,
                "pivot_x": 0.5,
                "pivot_y": 0.5,
                "resample_mode": None,
            },
        )
        normalized_tiles.append(normalized)
    migrated["tiles"] = normalized_tiles
    sources = migrated.get("sources")
    if not isinstance(sources, list):
        sources = []
    if not sources:
        legacy_sources = migrated.get("video_sources")
        if isinstance(legacy_sources, list) and legacy_sources:
            for index, entry in enumerate(legacy_sources):
                if not isinstance(entry, dict) or not entry.get("path"):
                    continue
                sources.append(
                    {
                        "source_id": str(entry.get("source_id") or f"legacy-video-{index}"),
                        "source_type": "video",
                        "original_path": entry.get("path"),
                        "current_path": entry.get("path"),
                        "display_name": str(entry.get("display_name") or Path(str(entry["path"])).name),
                        "fingerprint_kind": entry.get("fingerprint_kind"),
                        "original_fingerprint": entry.get("fingerprint"),
                        "current_fingerprint": entry.get("fingerprint"),
                        "open": True,
                        "tab_order": index,
                        "settings": entry.get("video_settings", {}),
                        "view_state": {},
                        "availability": "available",
                    }
                )
        elif migrated.get("source_image_path"):
            path = migrated.get("source_image_path")
            sources.append(
                {
                    "source_id": str(migrated.get("source_id") or "legacy-image-0"),
                    "source_type": str(migrated.get("source_type") or "image"),
                    "original_path": path,
                    "current_path": path,
                    "display_name": Path(str(path)).name,
                    "fingerprint_kind": migrated.get("source_fingerprint_kind"),
                    "original_fingerprint": migrated.get("source_fingerprint"),
                    "current_fingerprint": migrated.get("source_fingerprint"),
                    "open": True,
                    "tab_order": 0,
                    "settings": dict(settings),
                    "view_state": {},
                    "availability": "available",
                }
            )
    if "sources" in data:
        migrated["sources"] = sources
        migrated["active_source_id"] = migrated.get("active_source_id") or (sources[0].get("source_id") if sources else None)
        migrated["schema_version"] = 4
    else:
        migrated["schema_version"] = 3
    return migrated

from __future__ import annotations

from copy import deepcopy


def migrate_project_data(data: dict[str, object]) -> dict[str, object]:
    migrated = deepcopy(data)
    version = int(migrated.get("schema_version", 2))
    if version == 3:
        return migrated
    if version != 2:
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
    migrated["schema_version"] = 3
    return migrated

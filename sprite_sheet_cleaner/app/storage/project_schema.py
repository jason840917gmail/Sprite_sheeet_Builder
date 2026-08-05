from __future__ import annotations

from pathlib import PurePosixPath


SCHEMA_VERSION = 2
MAX_ENTRIES = 20_000
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ENTRY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024
MAX_TILE_DIMENSION = 16_384
MAX_TILE_PIXELS = 64_000_000
MAX_PROJECT_TILE_PIXELS = 2_000_000_000


def validate_entry_name(name: str) -> None:
    if not name or "\\" in name or name.startswith("/") or ":" in name:
        raise ValueError(f"Unsafe project archive entry: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe project archive entry: {name!r}")
    if name != "project.json" and not (name.startswith("tiles/") and name.endswith(".png")):
        raise ValueError(f"Unexpected project archive entry: {name!r}")

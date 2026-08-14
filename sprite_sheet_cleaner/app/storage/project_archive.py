from __future__ import annotations

from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from PIL import Image

from sprite_sheet_cleaner.app.storage.project_schema import (
    MAX_ENTRIES,
    MAX_ENTRY_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_PROJECT_TILE_PIXELS,
    MAX_TILE_DIMENSION,
    MAX_TILE_PIXELS,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    SCHEMA_VERSION,
    validate_entry_name,
)
from sprite_sheet_cleaner.app.storage.project_migrations import migrate_project_data


@dataclass(slots=True)
class LoadedProjectArchive:
    data: dict[str, object]
    tile_images: dict[str, Image.Image]


def _validate_image(image: Image.Image, total_pixels: int) -> int:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0 or width > MAX_TILE_DIMENSION or height > MAX_TILE_DIMENSION:
        raise ValueError("Project tile dimensions exceed the safety limit.")
    pixels = width * height
    if pixels > MAX_TILE_PIXELS or total_pixels + pixels > MAX_PROJECT_TILE_PIXELS:
        raise ValueError("Project tile pixel count exceeds the safety limit.")
    return total_pixels + pixels


def save_project_archive(
    path: str | Path,
    data: dict[str, object],
    tile_images: dict[str, Image.Image],
    *,
    keep_backup: bool = True,
) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".sscproj":
        target = target.with_suffix(".sscproj")
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(data)
    # Keep bare legacy manifests on their historical schema. New workspace
    # manifests always carry an explicit source registry and use schema 4.
    manifest["schema_version"] = SCHEMA_VERSION if "sources" in manifest else 3
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError("Project manifest is too large.")

    tile_refs = manifest.get("tiles", [])
    if not isinstance(tile_refs, list):
        raise ValueError("Project tiles must be a list.")
    declared_ids = {
        str(item.get("tile_id"))
        for item in tile_refs
        if isinstance(item, dict) and item.get("tile_id") is not None
    }
    if declared_ids != set(tile_images):
        raise ValueError("Project tile metadata and snapshot assets do not match.")

    total_pixels = 0
    encoded_tiles: dict[str, bytes] = {}
    for tile_id, image in tile_images.items():
        total_pixels = _validate_image(image, total_pixels)
        output = io.BytesIO()
        image.convert("RGBA").save(output, format="PNG")
        encoded = output.getvalue()
        if len(encoded) > MAX_ENTRY_BYTES:
            raise ValueError("Project tile asset is too large.")
        encoded_tiles[tile_id] = encoded

    temporary_fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.json", manifest_bytes)
            for tile_id, encoded in encoded_tiles.items():
                archive.writestr(f"tiles/{tile_id}.png", encoded)
        with zipfile.ZipFile(temporary, "r") as archive:
            _validate_archive_members(archive)
        if keep_backup and target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def load_project_archive(path: str | Path) -> LoadedProjectArchive:
    source = Path(path)
    with zipfile.ZipFile(source, "r") as archive:
        _validate_archive_members(archive)
        manifest_bytes = archive.read("project.json")
        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise ValueError("Project manifest is too large.")
        data = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Project manifest must be an object.")
        source_version = int(data.get("schema_version", 0))
        if source_version not in {2, 3, SCHEMA_VERSION}:
            raise ValueError(f"Unsupported project schema: {data.get('schema_version')}")
        data = migrate_project_data(data)
        tile_refs = data.get("tiles", [])
        if not isinstance(tile_refs, list):
            raise ValueError("Project tiles must be a list.")
        tile_images: dict[str, Image.Image] = {}
        total_pixels = 0
        for item in tile_refs:
            if not isinstance(item, dict) or not item.get("tile_id"):
                raise ValueError("Each project tile needs a tile_id.")
            tile_id = str(item["tile_id"])
            entry = f"tiles/{tile_id}.png"
            try:
                encoded = archive.read(entry)
            except KeyError as exc:
                raise ValueError(f"Missing tile snapshot: {tile_id}") from exc
            with Image.open(io.BytesIO(encoded)) as image:
                image.load()
                total_pixels = _validate_image(image, total_pixels)
                tile_images[tile_id] = image.convert("RGBA").copy()
        return LoadedProjectArchive(data=data, tile_images=tile_images)


def _validate_archive_members(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ValueError("Project archive contains too many entries.")
    names: set[str] = set()
    total_uncompressed = 0
    for info in infos:
        validate_entry_name(info.filename)
        if info.filename in names:
            raise ValueError(f"Duplicate project archive entry: {info.filename}")
        names.add(info.filename)
        if info.is_dir():
            raise ValueError("Project archives may not contain directory entries.")
        if info.file_size > MAX_ENTRY_BYTES:
            raise ValueError("Project archive entry is too large.")
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("Project archive is too large.")
    if "project.json" not in names:
        raise ValueError("Project archive is missing project.json.")

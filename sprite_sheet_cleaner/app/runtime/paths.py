from __future__ import annotations

import os
from pathlib import Path


APP_DATA_NAME = "SpriteSheetCleaner"


def app_data_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DATA_NAME
    return Path.home() / ".local" / "share" / APP_DATA_NAME


def runtime_root() -> Path:
    return app_data_root() / "runtimes"


def model_root() -> Path:
    return app_data_root() / "models"


def cache_root() -> Path:
    return app_data_root() / "cache"


def download_root() -> Path:
    return app_data_root() / "downloads"


def owned_leaf(root: Path, identifier: str) -> Path:
    if not identifier or any(character in identifier for character in "\\/:"):
        raise ValueError("Managed identifier must be a simple path component.")
    target = (root / identifier).resolve()
    resolved_root = root.resolve()
    if target == resolved_root or resolved_root not in target.parents:
        raise ValueError("Managed target must be a child of its root.")
    return target


def assert_owned_leaf(root: Path, target: Path, identifier: str) -> None:
    expected = owned_leaf(root, identifier)
    if target.resolve() != expected:
        raise ValueError("Managed target is outside its expected leaf directory.")
    if target.is_symlink():
        raise ValueError("Managed target may not be a link or reparse point.")

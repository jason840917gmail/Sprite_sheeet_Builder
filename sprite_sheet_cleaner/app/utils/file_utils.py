from __future__ import annotations

from pathlib import Path
import re


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "tile"


def ensure_png_suffix(path: Path) -> Path:
    if path.suffix.lower() != ".png":
        return path.with_suffix(".png")
    return path


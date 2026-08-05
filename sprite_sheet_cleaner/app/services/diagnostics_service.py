from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import tempfile


def collect_diagnostics(*, capabilities: object | None = None, runtimes: list[dict[str, object]] | None = None) -> dict[str, object]:
    """Return sanitized diagnostics; source pixels and absolute project paths are excluded."""

    data: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app": "SpriteSheetCleaner",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }
    if capabilities is not None:
        data["capabilities"] = {
            "onnxruntime_available": bool(getattr(capabilities, "onnxruntime_available", False)),
            "execution_providers": list(getattr(capabilities, "execution_providers", ())),
            "nvidia_device_count": len(getattr(capabilities, "nvidia_devices", ())),
            "warnings": list(getattr(capabilities, "warnings", ())),
        }
    data["runtimes"] = runtimes or []
    return data


def write_diagnostics(path: str | Path, data: dict[str, object]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    import os

    os.close(fd)
    temporary = Path(temp_name)
    try:
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(target)
        return target
    finally:
        if temporary.exists():
            temporary.unlink()


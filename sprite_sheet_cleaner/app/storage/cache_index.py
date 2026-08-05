from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(slots=True)
class CacheEntry:
    key: str
    path: str
    size_bytes: int
    kind: str = "preview"
    protected: bool = False
    last_accessed: str = ""

    def touch(self) -> None:
        self.last_accessed = datetime.now(timezone.utc).isoformat()


class CacheIndex:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, CacheEntry] = {}

    def add(self, entry: CacheEntry) -> None:
        if entry.size_bytes < 0:
            raise ValueError("Cache entry size cannot be negative.")
        if not entry.last_accessed:
            entry.touch()
        self.entries[entry.key] = entry

    def remove(self, key: str) -> None:
        self.entries.pop(key, None)

    @property
    def total_bytes(self) -> int:
        return sum(max(0, item.size_bytes) for item in self.entries.values())

    def evict_to_limit(self, limit_bytes: int, *, unlink=lambda path: Path(path).unlink()) -> list[str]:
        if limit_bytes < 0:
            raise ValueError("Cache limit cannot be negative.")
        removed: list[str] = []
        candidates = sorted(
            (item for item in self.entries.values() if not item.protected),
            key=lambda item: item.last_accessed,
        )
        for entry in candidates:
            if self.total_bytes <= limit_bytes:
                break
            try:
                unlink(entry.path)
            except FileNotFoundError:
                pass
            self.remove(entry.key)
            removed.append(entry.key)
        return removed

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(entry) for entry in self.entries.values()], indent=2), encoding="utf-8")
        return self.path

    def load(self) -> "CacheIndex":
        if not self.path.exists():
            return self
        values = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("Cache index must contain a list.")
        self.entries = {str(item["key"]): CacheEntry(**item) for item in values if isinstance(item, dict)}
        return self


from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from PIL import Image

from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.services.source_repository import SourceRepository


@dataclass(slots=True)
class SourceRecord:
    source_id: str = field(default_factory=lambda: uuid4().hex)
    source_type: str = "image"
    original_path: str | None = None
    current_path: str | None = None
    display_name: str = "Untitled source"
    fingerprint_kind: str | None = None
    original_fingerprint: str | None = None
    current_fingerprint: str | None = None
    source_size: tuple[int, int] | None = None
    open: bool = True
    tab_order: int | None = 0
    settings: dict[str, object] = field(default_factory=dict)
    view_state: dict[str, object] = field(default_factory=dict)
    availability: str = "available"

    @property
    def path(self) -> Path | None:
        return Path(self.current_path) if self.current_path else None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "original_path": self.original_path,
            "current_path": self.current_path,
            "display_name": self.display_name,
            "fingerprint_kind": self.fingerprint_kind,
            "original_fingerprint": self.original_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "source_size": list(self.source_size) if self.source_size else None,
            "open": self.open,
            "tab_order": self.tab_order,
            "settings": dict(self.settings),
            "view_state": dict(self.view_state),
            "availability": self.availability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SourceRecord":
        size = data.get("source_size")
        source_size = (int(size[0]), int(size[1])) if isinstance(size, (list, tuple)) and len(size) == 2 else None
        return cls(
            source_id=str(data.get("source_id") or uuid4().hex),
            source_type=str(data.get("source_type") or "image"),
            original_path=str(data.get("original_path")) if data.get("original_path") else None,
            current_path=str(data.get("current_path")) if data.get("current_path") else None,
            display_name=str(data.get("display_name") or "Untitled source"),
            fingerprint_kind=str(data.get("fingerprint_kind")) if data.get("fingerprint_kind") else None,
            original_fingerprint=str(data.get("original_fingerprint")) if data.get("original_fingerprint") else None,
            current_fingerprint=str(data.get("current_fingerprint")) if data.get("current_fingerprint") else None,
            source_size=source_size,
            open=bool(data.get("open", True)),
            tab_order=int(data["tab_order"]) if data.get("tab_order") is not None else None,
            settings=dict(data.get("settings")) if isinstance(data.get("settings"), dict) else {},
            view_state=dict(data.get("view_state")) if isinstance(data.get("view_state"), dict) else {},
            availability=str(data.get("availability") or "available"),
        )


@dataclass(slots=True)
class ImageDocument:
    record: SourceRecord
    image: Image.Image
    repository: SourceRepository
    settings: AppSettings

    def __post_init__(self) -> None:
        self.image = self.image.convert("RGBA").copy()

    @property
    def source_id(self) -> str:
        return self.record.source_id

    @property
    def path(self) -> Path | None:
        return self.record.path

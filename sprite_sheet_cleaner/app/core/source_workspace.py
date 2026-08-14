from __future__ import annotations

from pathlib import Path

from sprite_sheet_cleaner.app.models.source_document import SourceRecord


def canonical_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).casefold()


class SourceWorkspace:
    """Small, UI-independent registry for unified image/video source tabs."""

    def __init__(self) -> None:
        self.records: dict[str, SourceRecord] = {}
        self.open_ids: list[str] = []
        self._reserved_paths: dict[str, str] = {}

    def find_by_canonical_path(self, path: str | Path) -> SourceRecord | None:
        key = canonical_path(path)
        for record in self.records.values():
            if record.current_path and canonical_path(record.current_path) == key:
                return record
        return None

    def reserve_path(self, path: str | Path, token: str) -> str | None:
        key = canonical_path(path)
        owner = self._reserved_paths.get(key)
        if owner is not None and owner != token:
            return owner
        existing = self.find_by_canonical_path(path)
        if existing is not None and existing.source_id != token:
            return existing.source_id
        self._reserved_paths[key] = token
        return None

    def release_path(self, path: str | Path, token: str) -> None:
        key = canonical_path(path)
        if self._reserved_paths.get(key) == token:
            self._reserved_paths.pop(key, None)

    def add(self, record: SourceRecord) -> None:
        if record.source_id in self.records:
            raise ValueError(f"Source ID already exists: {record.source_id}")
        if record.current_path and self.find_by_canonical_path(record.current_path) is not None:
            raise ValueError(f"Source path is already registered: {record.current_path}")
        record.open = True
        record.tab_order = len(self.open_ids)
        self.records[record.source_id] = record
        self.open_ids.append(record.source_id)

    def activate(self, source_id: str) -> SourceRecord:
        record = self.records[source_id]
        if not record.open:
            record.open = True
            record.tab_order = len(self.open_ids)
            self.open_ids.append(source_id)
        return record

    def close_tab(self, source_id: str) -> SourceRecord:
        record = self.records[source_id]
        if source_id in self.open_ids:
            self.open_ids.remove(source_id)
        record.open = False
        record.tab_order = None
        self._renumber()
        return record

    def remove_all(self) -> None:
        self.records.clear()
        self.open_ids.clear()
        self._reserved_paths.clear()

    def _renumber(self) -> None:
        for index, source_id in enumerate(self.open_ids):
            self.records[source_id].tab_order = index

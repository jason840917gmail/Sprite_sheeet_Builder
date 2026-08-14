from __future__ import annotations

from dataclasses import dataclass, field

from sprite_sheet_cleaner.app.models.source_asset import SourceAsset
from sprite_sheet_cleaner.app.models.source_revision import SourceRevision
from sprite_sheet_cleaner.app.models.tile_snapshot import TileSnapshot


@dataclass(slots=True)
class ProjectDocument:
    schema_version: int = 4
    source_asset: SourceAsset | None = None
    revisions: dict[str, SourceRevision] = field(default_factory=dict)
    active_revision_id: str | None = None
    candidate_revision_id: str | None = None
    tiles: list[TileSnapshot] = field(default_factory=list)
    dirty: bool = False

    @property
    def active_revision(self) -> SourceRevision | None:
        if self.active_revision_id is None:
            return None
        return self.revisions.get(self.active_revision_id)

    @property
    def candidate_revision(self) -> SourceRevision | None:
        if self.candidate_revision_id is None:
            return None
        return self.revisions.get(self.candidate_revision_id)

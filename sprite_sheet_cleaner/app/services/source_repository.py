from __future__ import annotations

from pathlib import Path

from PIL import Image

from sprite_sheet_cleaner.app.models.project_document import ProjectDocument
from sprite_sheet_cleaner.app.models.source_asset import SourceAsset
from sprite_sheet_cleaner.app.models.source_revision import SourceRevision


class SourceRepository:
    """Own immutable originals and candidate/active source revisions in memory."""

    def __init__(self, document: ProjectDocument | None = None) -> None:
        self.document = document or ProjectDocument()
        self._original_image: Image.Image | None = None

    def open_original(self, image: Image.Image, path: str | Path | None = None) -> SourceAsset:
        self._original_image = image.convert("RGBA").copy()
        self.document.source_asset = SourceAsset.from_image(self._original_image, path)
        self.document.revisions.clear()
        self.document.active_revision_id = None
        self.document.candidate_revision_id = None
        self.document.tiles.clear()
        self.document.dirty = True
        return self.document.source_asset

    def original_image(self) -> Image.Image:
        if self._original_image is None:
            raise ValueError("No original source image is open.")
        return self._original_image.copy()

    def create_candidate(
        self,
        processed_image: Image.Image,
        *,
        engine_id: str,
        settings: dict[str, object],
        model_id: str | None = None,
        backend: str | None = None,
    ) -> SourceRevision:
        source = self.document.source_asset
        if source is None:
            raise ValueError("Open a source image before creating a revision.")
        if self.document.candidate_revision_id is not None:
            old_candidate = self.document.revisions.get(self.document.candidate_revision_id)
            if old_candidate is not None:
                old_candidate.status = "archived"

        revision = SourceRevision(
            source_fingerprint=source.fingerprint,
            engine_id=engine_id,
            settings=dict(settings),
            processed_image=processed_image,
            model_id=model_id,
            backend=backend,
        )
        self.document.revisions[revision.revision_id] = revision
        self.document.candidate_revision_id = revision.revision_id
        self.document.dirty = True
        return revision

    def activate_candidate(self) -> SourceRevision:
        candidate = self.document.candidate_revision
        if candidate is None:
            raise ValueError("There is no completed source candidate to activate.")
        previous = self.document.active_revision
        if previous is not None:
            previous.status = "archived"
        candidate.status = "active"
        self.document.active_revision_id = candidate.revision_id
        self.document.candidate_revision_id = None
        self.document.dirty = True
        return candidate

    def discard_candidate(self) -> None:
        candidate_id = self.document.candidate_revision_id
        if candidate_id is None:
            return
        candidate = self.document.revisions.get(candidate_id)
        if candidate is not None:
            candidate.status = "archived"
        self.document.candidate_revision_id = None
        self.document.dirty = True

    def active_image(self) -> Image.Image:
        active = self.document.active_revision
        if active is None:
            return self.original_image()
        return active.processed_image.copy()

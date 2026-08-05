from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from PIL import Image


RevisionStatus = Literal["candidate", "active", "archived"]


@dataclass(slots=True)
class SourceRevision:
    source_fingerprint: str
    engine_id: str
    settings: dict[str, object]
    processed_image: Image.Image
    model_id: str | None = None
    backend: str | None = None
    revision_id: str = field(default_factory=lambda: uuid4().hex)
    status: RevisionStatus = "candidate"

    def __post_init__(self) -> None:
        self.processed_image = self.processed_image.convert("RGBA").copy()

    @property
    def size(self) -> tuple[int, int]:
        return self.processed_image.size

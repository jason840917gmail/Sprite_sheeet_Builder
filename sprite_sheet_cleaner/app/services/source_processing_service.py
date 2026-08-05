from __future__ import annotations

from PIL import Image

from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, process_crop
from sprite_sheet_cleaner.app.engines.base import BackgroundEngine
from sprite_sheet_cleaner.app.engines.postprocess import apply_matte
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.services.source_repository import SourceRepository


class SourceProcessingService:
    def __init__(self, repository: SourceRepository, engines: dict[str, BackgroundEngine]) -> None:
        self.repository = repository
        self.engines = dict(engines)

    def create_candidate(
        self,
        settings: object,
        *,
        engine_id: str | None = None,
        progress=None,
        cancelled=None,
    ):
        selected_id = engine_id or str(getattr(settings, "engine", "exact_key"))
        try:
            engine = self.engines[selected_id]
        except KeyError as exc:
            raise ValueError(f"Background engine is not available: {selected_id}") from exc
        source = self.repository.original_image()
        result = engine.remove(source, settings, progress=progress, cancelled=cancelled)
        processed = apply_matte(source, result)
        settings_data = dict(getattr(settings, "__dict__", {}))
        if not settings_data:
            for field_name in ("engine", "remove_background", "background_color", "tolerance", "edge_bleed"):
                if hasattr(settings, field_name):
                    settings_data[field_name] = getattr(settings, field_name)
        return self.repository.create_candidate(
            processed,
            engine_id=selected_id,
            settings=settings_data,
            backend=result.backend,
        )

    def extract_tile(
        self,
        crop_rect: tuple[int, int, int, int],
        settings: AppSettings,
        *,
        name: str | None = None,
    ):
        active = self.repository.document.active_revision
        if active is None:
            raise ValueError("Activate a processed source revision before extracting tiles.")
        normalized = clamp_crop_rect(active.processed_image, crop_rect)
        extraction_settings = AppSettings.from_dict(settings.to_dict())
        extraction_settings.remove_background = False
        image = process_crop(active.processed_image, normalized, extraction_settings)
        return image, normalized, active.revision_id, name

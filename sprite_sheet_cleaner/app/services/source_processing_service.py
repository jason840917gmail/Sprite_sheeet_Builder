from __future__ import annotations

from dataclasses import asdict, is_dataclass
from PIL import Image

from sprite_sheet_cleaner.app.core.image_processor import clamp_crop_rect, crop_source_image, process_crop
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
        settings_data = asdict(settings) if is_dataclass(settings) else dict(getattr(settings, "__dict__", {}))
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

    def process_frame(
        self,
        image: Image.Image,
        settings: object,
        *,
        progress=None,
        cancelled=None,
    ) -> Image.Image:
        """Apply one configured background engine while preserving source alpha."""
        source = image.convert("RGBA")
        if not bool(getattr(settings, "remove_background", True)):
            return source.copy()
        selected_id = str(getattr(settings, "engine", "exact_key"))
        try:
            engine = self.engines[selected_id]
        except KeyError as exc:
            raise ValueError(f"Background engine is not available: {selected_id}") from exc
        result = engine.remove(source, settings, progress=progress, cancelled=cancelled)
        return apply_matte(source, result)

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

    def process_tile(
        self,
        source_image: Image.Image,
        crop_rect: tuple[int, int, int, int],
        settings: AppSettings,
        *,
        progress=None,
        cancelled=None,
    ) -> Image.Image:
        """Create one final tile using the selected tile background engine."""
        settings.validated()
        normalized = clamp_crop_rect(source_image, crop_rect)
        crop = crop_source_image(source_image, normalized)
        if cancelled is not None and cancelled():
            raise RuntimeError("Tile processing cancelled.")

        if settings.remove_background:
            crop = self.process_frame(
                crop,
                settings.tile_processing_settings(),
                progress=progress,
                cancelled=cancelled,
            )

        extraction_settings = AppSettings.from_dict(settings.to_dict())
        extraction_settings.remove_background = False
        return process_crop(crop, (0, 0, crop.width, crop.height), extraction_settings)

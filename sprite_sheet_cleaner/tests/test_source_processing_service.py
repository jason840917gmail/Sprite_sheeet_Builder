from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.engines.base import MatteResult
from sprite_sheet_cleaner.app.engines.exact_key import ExactKeyEngine
from sprite_sheet_cleaner.app.engines.smart_solid import SmartSolidEngine
from sprite_sheet_cleaner.app.models.app_settings import AppSettings
from sprite_sheet_cleaner.app.models.source_processing_settings import SourceProcessingSettings
from sprite_sheet_cleaner.app.services.source_processing_service import SourceProcessingService
from sprite_sheet_cleaner.app.services.source_repository import SourceRepository


class CountingEngine:
    descriptor = ExactKeyEngine.descriptor

    def __init__(self) -> None:
        self.calls = 0

    def remove(self, image, settings, **_kwargs):
        self.calls += 1
        return ExactKeyEngine().remove(image, settings)


class SourceProcessingServiceTests(unittest.TestCase):
    def test_processing_runs_once_and_requires_activation_before_extraction(self) -> None:
        repository = SourceRepository()
        source = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        source.putpixel((2, 2), (20, 40, 60, 255))
        repository.open_original(source)
        engine = CountingEngine()
        service = SourceProcessingService(repository, {"exact_key": engine})
        settings = SourceProcessingSettings(tolerance=1)

        candidate = service.create_candidate(settings)
        self.assertEqual(candidate.settings["compute"], "auto")
        self.assertEqual(candidate.settings["transparent_threshold"], 24)
        self.assertEqual(candidate.settings["foreground_threshold"], 64)
        self.assertEqual(candidate.settings["edge_bleed"], 1)
        with self.assertRaises(ValueError):
            service.extract_tile((0, 0, 4, 4), AppSettings())
        repository.activate_candidate()
        first = service.extract_tile((0, 0, 4, 4), AppSettings())
        second = service.extract_tile((4, 4, 4, 4), AppSettings())

        self.assertEqual(engine.calls, 1)
        self.assertEqual(first[0].size, (256, 256))
        self.assertEqual(second[0].size, (256, 256))
        self.assertEqual(first[0].getpixel((128, 128))[3], 255)

    def test_process_tile_uses_selected_tile_background_engine(self) -> None:
        source = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        source.putpixel((2, 2), (20, 40, 60, 255))
        engine = CountingEngine()
        service = SourceProcessingService(SourceRepository(), {"smart_solid": engine})
        settings = AppSettings(
            tile_width=4,
            tile_height=4,
            remove_background=True,
            tile_background_engine="smart_solid",
        )

        tile = service.process_tile(source, (0, 0, 4, 4), settings)

        self.assertEqual(engine.calls, 1)
        self.assertEqual(tile.size, (4, 4))
        self.assertEqual(tile.getpixel((2, 2))[3], 255)
        self.assertEqual(tile.getpixel((0, 0))[3], 0)

    def test_process_frame_uses_shared_smart_solid_and_preserves_source_alpha(self) -> None:
        source = Image.new("RGBA", (5, 5), (255, 0, 255, 255))
        source.putpixel((2, 2), (20, 40, 60, 128))
        service = SourceProcessingService(SourceRepository(), {"smart_solid": SmartSolidEngine()})
        settings = SourceProcessingSettings(
            engine="smart_solid",
            background_color=(255, 0, 255),
            transparent_threshold=2,
            foreground_threshold=20,
        )

        result = service.process_frame(source, settings)

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((2, 2)), (20, 40, 60, 128))


if __name__ == "__main__":
    unittest.main()

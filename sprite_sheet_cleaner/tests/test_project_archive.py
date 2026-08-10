from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from sprite_sheet_cleaner.app.storage.project_archive import load_project_archive, save_project_archive


class ProjectArchiveTests(unittest.TestCase):
    def test_round_trip_preserves_hidden_rgb_and_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sprite.sscproj"
            image = Image.new("RGBA", (4, 4), (12, 34, 56, 0))
            image.putpixel((1, 1), (100, 50, 25, 128))
            data = {"source_image_path": "source.png", "tiles": [{"tile_id": "one", "name": "tile_001"}]}

            save_project_archive(path, data, {"one": image})
            loaded = load_project_archive(path)

            self.assertEqual(loaded.data["schema_version"], 3)
            self.assertEqual(loaded.tile_images["one"].getpixel((0, 0)), (12, 34, 56, 0))
            self.assertEqual(loaded.tile_images["one"].getpixel((1, 1)), (100, 50, 25, 128))

    def test_rejects_path_traversal_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.sscproj"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("project.json", json.dumps({"schema_version": 2, "tiles": []}))
                archive.writestr("../outside.txt", b"unsafe")

            with self.assertRaises(ValueError):
                load_project_archive(path)

    def test_save_creates_a_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sprite.sscproj"
            data = {"tiles": [{"tile_id": "one"}]}
            image = Image.new("RGBA", (1, 1), (1, 2, 3, 4))
            save_project_archive(path, data, {"one": image})
            save_project_archive(path, data, {"one": image})

            self.assertTrue(path.with_suffix(".sscproj.bak").exists())

    def test_schema_two_archive_migrates_selection_size_to_bucket_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sscproj"
            image = Image.new("RGBA", (64, 32), (1, 2, 3, 255))
            encoded = io.BytesIO()
            image.save(encoded, "PNG")
            manifest = {
                "schema_version": 2,
                "settings": {
                    "tile_width": 64,
                    "tile_height": 32,
                    "scale_mode": "scale_down_only",
                },
                "tiles": [{"tile_id": "legacy", "source_rect": [0, 0, 64, 32]}],
            }
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("project.json", json.dumps(manifest))
                archive.writestr("tiles/legacy.png", encoded.getvalue())

            loaded = load_project_archive(path)

            self.assertEqual(loaded.data["schema_version"], 3)
            self.assertEqual(loaded.data["settings"]["bucket_tile_width"], 64)
            self.assertEqual(loaded.data["settings"]["bucket_tile_height"], 32)
            self.assertEqual(loaded.data["settings"]["bucket_resize_mode"], "fit_down_only")
            self.assertEqual(loaded.data["tiles"][0]["transform"]["angle_degrees"], 0.0)


if __name__ == "__main__":
    unittest.main()

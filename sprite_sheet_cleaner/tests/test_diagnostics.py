from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sprite_sheet_cleaner.app.services.diagnostics_service import collect_diagnostics, write_diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_diagnostics_are_sanitized(self) -> None:
        data = collect_diagnostics(runtimes=[{"runtime_id": "ben2", "state": "ready"}])
        self.assertNotIn("source_image_path", json.dumps(data))
        with tempfile.TemporaryDirectory() as directory:
            path = write_diagnostics(Path(directory) / "diagnostics.json", data)
            self.assertTrue(path.is_file())


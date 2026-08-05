from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from sprite_sheet_cleaner.app.storage.cache_index import CacheEntry, CacheIndex


class CacheIndexTests(unittest.TestCase):
    def test_evicts_old_unprotected_entries_and_keeps_protected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = CacheIndex(Path(directory) / "cache.json")
            index.add(CacheEntry("old", str(Path(directory) / "old"), 10, last_accessed="2020-01-01"))
            index.add(CacheEntry("protected", str(Path(directory) / "protected"), 10, protected=True, last_accessed="2019-01-01"))
            removed = index.evict_to_limit(5, unlink=lambda _path: None)
            self.assertEqual(removed, ["old"])
            self.assertIn("protected", index.entries)

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            index = CacheIndex(path)
            index.add(CacheEntry("one", "one.png", 2))
            index.save()
            loaded = CacheIndex(path).load()
            self.assertEqual(loaded.entries["one"].size_bytes, 2)


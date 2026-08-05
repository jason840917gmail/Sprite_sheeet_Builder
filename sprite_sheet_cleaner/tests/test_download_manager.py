from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest

from sprite_sheet_cleaner.app.runtime.download_manager import download_verified, sha256_file


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = io.BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)


class DownloadManagerTests(unittest.TestCase):
    def test_download_verifies_checksum_and_replaces_atomically(self) -> None:
        payload = b"verified model fixture"
        import hashlib

        checksum = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "model.onnx"
            progress: list[float] = []
            result = download_verified(
                "https://example.test/model.onnx",
                target,
                checksum,
                progress=progress.append,
                opener=lambda _request: _Response(payload),
            )

            self.assertEqual(result, target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(sha256_file(target), checksum)
            self.assertEqual(progress[-1], 1.0)

    def test_download_rejects_bad_checksum_and_leaves_no_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "model.onnx"
            with self.assertRaises(ValueError):
                download_verified(
                    "https://example.test/model.onnx",
                    target,
                    "0" * 64,
                    opener=lambda _request: _Response(b"wrong"),
                )
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

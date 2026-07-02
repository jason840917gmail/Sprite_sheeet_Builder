from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    entry = Path(__file__).parent / "app" / "main.py"
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "SpriteSheetCleaner",
            "--windowed",
            str(entry),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())


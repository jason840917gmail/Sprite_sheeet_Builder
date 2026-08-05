from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    entry = Path(__file__).parent / "app" / "main.py"
    help_dir = Path(__file__).parents[1] / "help"
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "SpriteSheetCleaner",
            "--windowed",
            "--add-data",
            f"{help_dir}{os.pathsep}help",
            str(entry),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())


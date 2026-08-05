from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SheetSettings:
    sheet_columns: int = 8
    sheet_rows: int = 8
    match_sheet_to_grid: bool = False

    def validated(self) -> "SheetSettings":
        if self.sheet_columns <= 0 or self.sheet_rows <= 0:
            raise ValueError("Final tilesheet dimensions must be positive.")
        return self

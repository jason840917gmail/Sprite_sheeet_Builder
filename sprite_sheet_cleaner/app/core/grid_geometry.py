from __future__ import annotations

from dataclasses import dataclass


Point = tuple[float, float]
Cell = tuple[int, int]
Rect = tuple[int, int, int, int]
Origin = tuple[int, int]


@dataclass(frozen=True, slots=True)
class GridSpec:
    image_width: int
    image_height: int
    tile_width: int
    tile_height: int
    columns: int
    rows: int

    @property
    def cell_count(self) -> int:
        return self.columns * self.rows

    @property
    def image_size(self) -> tuple[int, int]:
        return self.image_width, self.image_height

    @property
    def tile_size(self) -> tuple[int, int]:
        return self.tile_width, self.tile_height

    @property
    def grid_width(self) -> int:
        return self.columns * self.tile_width

    @property
    def grid_height(self) -> int:
        return self.rows * self.tile_height

    @property
    def leftover_width(self) -> int:
        return self.image_width - self.grid_width

    @property
    def leftover_height(self) -> int:
        return self.image_height - self.grid_height

    @property
    def has_leftover_pixels(self) -> bool:
        return self.leftover_width > 0 or self.leftover_height > 0


def calculate_grid(
    image_size: tuple[int, int],
    tile_size: tuple[int, int],
) -> GridSpec:
    image_width, image_height = (int(value) for value in image_size)
    tile_width, tile_height = (int(value) for value in tile_size)

    if image_width <= 0 or image_height <= 0:
        raise ValueError("Open a source image before using the Grid tool.")
    if tile_width <= 0 or tile_height <= 0:
        raise ValueError("Grid tile dimensions must be positive.")
    if tile_width > image_width or tile_height > image_height:
        raise ValueError(
            f"Tile size {tile_width}x{tile_height} is larger than image {image_width}x{image_height}."
        )
    columns = image_width // tile_width
    rows = image_height // tile_height
    if columns <= 0 or rows <= 0:
        raise ValueError(
            f"Tile size {tile_width}x{tile_height} does not fit inside image {image_width}x{image_height}."
        )

    return GridSpec(
        image_width=image_width,
        image_height=image_height,
        tile_width=tile_width,
        tile_height=tile_height,
        columns=columns,
        rows=rows,
    )


def clamp_grid_origin(grid: GridSpec, origin: Origin) -> Origin:
    x, y = (int(value) for value in origin)
    return (
        min(max(x, 0), max(grid.leftover_width, 0)),
        min(max(y, 0), max(grid.leftover_height, 0)),
    )


def cell_rect(grid: GridSpec, column: int, row: int, origin: Origin = (0, 0)) -> Rect:
    column = int(column)
    row = int(row)
    if not 0 <= column < grid.columns or not 0 <= row < grid.rows:
        raise ValueError(f"Grid cell {column},{row} is outside the grid.")
    origin_x, origin_y = clamp_grid_origin(grid, origin)
    return (
        origin_x + column * grid.tile_width,
        origin_y + row * grid.tile_height,
        grid.tile_width,
        grid.tile_height,
    )


def cell_at_point(grid: GridSpec, point: Point, origin: Origin = (0, 0)) -> Cell | None:
    x, y = point
    origin_x, origin_y = clamp_grid_origin(grid, origin)
    grid_right = origin_x + grid.grid_width
    grid_bottom = origin_y + grid.grid_height
    if x < origin_x or y < origin_y or x >= grid_right or y >= grid_bottom:
        return None
    return int(x - origin_x) // grid.tile_width, int(y - origin_y) // grid.tile_height


def rect_cell(grid: GridSpec, rect: Rect, origin: Origin = (0, 0)) -> Cell | None:
    x, y, width, height = (int(value) for value in rect)
    origin_x, origin_y = clamp_grid_origin(grid, origin)
    if width != grid.tile_width or height != grid.tile_height:
        return None
    local_x = x - origin_x
    local_y = y - origin_y
    if local_x < 0 or local_y < 0:
        return None
    if local_x % grid.tile_width != 0 or local_y % grid.tile_height != 0:
        return None
    column = local_x // grid.tile_width
    row = local_y // grid.tile_height
    if not 0 <= column < grid.columns or not 0 <= row < grid.rows:
        return None
    return column, row

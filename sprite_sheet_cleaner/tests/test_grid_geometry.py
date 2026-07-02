from __future__ import annotations

import unittest

from sprite_sheet_cleaner.app.core.grid_geometry import (
    calculate_grid,
    cell_at_point,
    cell_rect,
    clamp_grid_origin,
    rect_cell,
)


class GridGeometryTests(unittest.TestCase):
    def test_calculate_grid_returns_exact_dimensions(self) -> None:
        grid = calculate_grid((1024, 768), (256, 256))

        self.assertEqual(grid.columns, 4)
        self.assertEqual(grid.rows, 3)
        self.assertEqual(grid.cell_count, 12)
        self.assertEqual(grid.image_size, (1024, 768))
        self.assertEqual(grid.tile_size, (256, 256))

    def test_calculate_grid_rounds_down_uneven_tile_size(self) -> None:
        grid = calculate_grid((1000, 768), (256, 256))

        self.assertEqual(grid.columns, 3)
        self.assertEqual(grid.rows, 3)
        self.assertEqual(grid.grid_width, 768)
        self.assertEqual(grid.grid_height, 768)
        self.assertEqual(grid.leftover_width, 232)
        self.assertEqual(grid.leftover_height, 0)
        self.assertTrue(grid.has_leftover_pixels)

    def test_calculate_grid_rejects_tile_larger_than_image(self) -> None:
        with self.assertRaisesRegex(ValueError, "larger than image"):
            calculate_grid((128, 128), (256, 256))

    def test_cell_rect_uses_row_and_column_offsets(self) -> None:
        grid = calculate_grid((512, 512), (128, 256))

        self.assertEqual(cell_rect(grid, 2, 1), (256, 256, 128, 256))

    def test_cell_rect_uses_grid_origin(self) -> None:
        grid = calculate_grid((1000, 768), (256, 256))

        self.assertEqual(cell_rect(grid, 0, 0, (232, 0)), (232, 0, 256, 256))
        self.assertEqual(cell_rect(grid, 2, 2, (232, 0)), (744, 512, 256, 256))

    def test_cell_at_point_returns_none_outside_image(self) -> None:
        grid = calculate_grid((512, 512), (128, 128))

        self.assertEqual(cell_at_point(grid, (127.9, 128)), (0, 1))
        self.assertEqual(cell_at_point(grid, (512, 128)), None)
        self.assertEqual(cell_at_point(grid, (-1, 128)), None)

    def test_cell_at_point_returns_none_in_leftover_area(self) -> None:
        grid = calculate_grid((1000, 768), (256, 256))

        self.assertEqual(cell_at_point(grid, (767.9, 100)), (2, 0))
        self.assertEqual(cell_at_point(grid, (768, 100)), None)

    def test_cell_at_point_uses_grid_origin(self) -> None:
        grid = calculate_grid((1000, 768), (256, 256))

        self.assertEqual(cell_at_point(grid, (231.9, 100), (232, 0)), None)
        self.assertEqual(cell_at_point(grid, (232, 100), (232, 0)), (0, 0))
        self.assertEqual(cell_at_point(grid, (999.9, 100), (232, 0)), (2, 0))

    def test_rect_cell_accepts_only_aligned_cells(self) -> None:
        grid = calculate_grid((512, 512), (128, 128))

        self.assertEqual(rect_cell(grid, (256, 128, 128, 128)), (2, 1))
        self.assertEqual(rect_cell(grid, (250, 128, 128, 128)), None)
        self.assertEqual(rect_cell(grid, (256, 128, 64, 128)), None)

    def test_rect_cell_uses_grid_origin(self) -> None:
        grid = calculate_grid((1000, 768), (256, 256))

        self.assertEqual(rect_cell(grid, (232, 0, 256, 256), (232, 0)), (0, 0))
        self.assertEqual(rect_cell(grid, (0, 0, 256, 256), (232, 0)), None)

    def test_clamp_grid_origin_stays_inside_image_bounds(self) -> None:
        grid = calculate_grid((1000, 770), (256, 256))

        self.assertEqual(clamp_grid_origin(grid, (-10, -10)), (0, 0))
        self.assertEqual(clamp_grid_origin(grid, (500, 500)), (232, 2))


if __name__ == "__main__":
    unittest.main()

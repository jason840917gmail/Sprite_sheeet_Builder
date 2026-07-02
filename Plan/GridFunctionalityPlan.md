# Grid Functionality Development Plan

Created: 2026-07-02

## Goal

Add a Grid tool that automatically divides the loaded source image into equal, non-overlapping tile cells using the current tile selection size. If the image size does not divide evenly, round the grid down to the full cells that fit and leave the leftover right/bottom pixels outside the clickable grid. After the grid is visible, the user can click specific cells to add those exact tiles to the bucket.

## Understanding

The current app already has:

- Pointer tool for panning.
- Select tool for placing one fixed-size tile box.
- Tile width and height settings that define the selection size.
- Bucket logic that can add a tile from any crop rectangle.

The new Grid tool should use the same tile width and tile height, but instead of placing one box manually, it should generate every full cell that fits inside the source image:

```text
columns = source_image_width / tile_width
rows = source_image_height / tile_height
```

The grid rounds down when the divisions are not exact:

```text
columns = source_image_width // tile_width
rows = source_image_height // tile_height
```

The app should not create partial cells. Leftover pixels on the right or bottom remain visible in the source image, but they are not part of the clickable grid.

## User Workflow

1. User opens a sprite sheet.
2. User sets the tile / selection size.
3. User chooses the Grid tool from the left toolbar or Tools menu.
4. The source viewer calculates how many full tile cells fit.
5. If valid, a grid overlay appears over the source image.
6. User clicks a cell.
7. The app adds that cell rectangle to the bucket using the existing crop pipeline.
8. User can right-click and hold to drag the fitted grid within the source image boundaries.
9. The clicked cell is visually marked as already added.
10. The final preview updates as usual.

## UX Rules

- Add a third tool: `Grid`.
- Suggested shortcut: `G`.
- Grid uses the current tile width and height from Settings.
- Grid cells cover only the image bounds, not the pasteboard area.
- Clicking outside the image does nothing.
- Clicking a valid grid cell adds that cell to the bucket.
- Right-click and hold drags the fitted grid within the source image boundaries.
- Grid drag clamps to the available leftover right/bottom space so the grid never extends past the image.
- Grid mode should advise: `Left click tile; right click and hold to drag grid`.
- Already-added grid cells should be shown with a subtle filled overlay.
- The cell under the cursor should have a hover outline.
- If the bucket is full, clicking a grid cell should show the existing bucket-full warning.
- If the grid leaves leftover pixels, show a clear status message:

```text
Ready 3 x 3 (rounded down, leftover 232px right)
```

## Validation Rules

Create a small grid-geometry helper so the logic can be unit-tested outside Qt:

```python
def calculate_grid(image_size: tuple[int, int], tile_size: tuple[int, int]) -> GridSpec:
    ...
```

`GridSpec` should include:

- `image_width`
- `image_height`
- `tile_width`
- `tile_height`
- `columns`
- `rows`
- `cell_count`

Invalid cases:

- No image loaded.
- Tile width or height is less than 1.
- Tile width is larger than the image width.
- Tile height is larger than the image height.

Cell rectangle formula:

```python
x = column * tile_width
y = row * tile_height
rect = (x, y, tile_width, tile_height)
```

This guarantees no overlap and no partial cells.

## Code Touch Points

### `sprite_sheet_cleaner/app/core/grid_geometry.py`

Add a new helper module for deterministic grid math:

- `GridSpec` dataclass.
- `calculate_grid(...)`.
- `cell_at_point(...)`.
- `cell_rect(...)`.

### `sprite_sheet_cleaner/app/widgets/source_viewer.py`

Extend the viewer tool model:

- Change `ViewerTool` from `Literal["pointer", "select"]` to include `"grid"`.
- Add a grid overlay item, preferably a `QGraphicsPathItem`.
- Add a hover cell item.
- Add an added-cell overlay item or tracked rect collection.
- Add signal:

```python
gridCellClicked = Signal(object)
```

The signal should emit a crop rect:

```python
(x, y, tile_width, tile_height)
```

Add public methods:

- `set_grid_enabled(...)` or make grid visibility derive from active tool.
- `set_grid_added_rects(...)` so the viewer can mark cells already in the bucket.
- `grid_is_valid()` or expose validation status for the main window.

Mouse behavior:

- Pointer tool: unchanged.
- Select tool: unchanged.
- Grid tool:
  - left click emits the clicked cell rect.
  - mouse move updates the hover cell.
  - middle/right drag can still pan.

### `sprite_sheet_cleaner/app/main_window.py`

Add UI wiring:

- Create `grid_action` in the toolbar and Tools menu.
- Add it to the existing exclusive `QActionGroup`.
- Connect it to `_set_viewer_tool("grid")`.
- Connect `source_viewer.gridCellClicked` to a new `_add_grid_cell_to_bucket(rect)` method.

Reuse existing add logic as much as possible:

- Check image exists.
- Check bucket capacity.
- Call `self.model.add_tile_from_crop(self.source_image, rect)`.
- Refresh bucket and preview.
- Show status like:

```text
Added grid tile row 3, column 5
```

When settings change:

- Continue updating `source_viewer.set_fixed_selection_size(...)`.
- Also rebuild/revalidate the grid overlay when the current tool is Grid.

When image changes:

- Clear selection.
- Rebuild grid overlay if Grid is active.
- Clear any visual added-cell markers that no longer apply.

### `sprite_sheet_cleaner/app/widgets/settings_panel.py`

No major layout change required for MVP. The existing tile width/height fields define the grid cell size.

Optional small polish:

- Add a status label near tile size only if the invalid-grid message is too easy to miss in the status bar.

### `sprite_sheet_cleaner/app/core/project_model.py`

No schema change is needed for the MVP because grid-selected tiles are still normal bucket tiles with `source_rect`.

Optional later:

- Add source metadata such as `"source_mode": "grid"` to tile project data if we want to distinguish grid tiles from manually selected tiles.

## Visual Design

Use restrained colors that fit the current viewer:

- Grid lines: thin light blue or neutral gray with transparency.
- Hover cell: blue outline, light transparent fill.
- Added cell: green or blue transparent fill.
- Current manual selection rectangle remains unchanged.

Grid overlay must remain aligned with image pixels at all zoom levels.

## Edge Cases

- Tile size equals image size: valid 1x1 grid.
- Source image has dimensions like `1024x768` and tile is `256x256`: valid `4x3` grid.
- Source image `1000x768` and tile `256x256`: valid `3x3` grid with 232 leftover pixels on the right.
- Bucket full: no add, existing warning.
- Background removal, trim, padding, scale mode: keep using existing processing settings after the cell is cropped.
- Duplicate clicks on same cell:
  - MVP recommendation: do not add the same grid cell twice unless the user uses Duplicate in the bucket.
  - If clicked again, select/highlight the existing bucket item if practical; otherwise show a short status message.

## Implementation Phases

### Phase 1 - Grid Math

- Add `grid_geometry.py`.
- Add unit tests for valid grid calculation.
- Add unit tests for rounded-down uneven dimensions.
- Add unit tests for point-to-cell and cell-to-rect conversion.

### Phase 2 - Source Viewer Overlay

- Extend viewer tools with `"grid"`.
- Draw the grid overlay when Grid is active and the image/tile size is valid.
- Draw hover cell feedback.
- Emit `gridCellClicked` with exact crop rects.
- Keep pointer/select behavior unchanged.

### Phase 3 - Main Window Wiring

- Add Grid action to toolbar and Tools menu.
- Add shortcut `G`.
- Route Grid clicks into the existing bucket add pipeline.
- Refresh added-cell markers after add/delete/load/clear/reprocess.
- Update status text to include Grid as a tool.

### Phase 4 - Grid Feedback

- Show clear status when Grid is selected, including leftover pixels after rounding down.
- Show a warning only when no full grid cell can fit.
- Revalidate when:
  - image changes
  - tile width changes
  - tile height changes
  - tool changes to Grid

### Phase 5 - Verification

- Run:

```powershell
python -m unittest discover -s sprite_sheet_cleaner\tests
python -m compileall -q sprite_sheet_cleaner
```

- Add an offscreen Qt smoke test if practical:
  - Create main window.
  - Set source image to `512x512`.
  - Set tile size to `256x256`.
  - Activate Grid tool.
  - Confirm grid action exists and viewer accepts grid mode.

## Acceptance Criteria

- Grid tool appears beside Pointer and Select.
- Grid mode draws a full grid over a compatible source image.
- Grid mode rounds down uneven image dimensions and reports leftover pixels.
- Clicking a grid cell adds that exact source tile to the bucket.
- No generated grid cell overlaps another cell.
- No generated grid cell extends past the source image.
- Existing Select and Pointer tools continue working.
- Existing project save/load still works for grid-added tiles.
- Automated tests pass.

## Later Enhancements

- Shift-click or drag to add multiple grid cells.
- Select a rectangle of grid cells and add them in row-major order.
- Auto-fill bucket with all grid cells.
- Context menu on a grid cell: add, preview, rename, ignore.
- Show row/column coordinates in the status bar while hovering.
- Add a grid visibility toggle independent from Grid tool mode.

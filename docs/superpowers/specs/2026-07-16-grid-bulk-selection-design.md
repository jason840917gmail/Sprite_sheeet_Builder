# Grid Bulk Selection and Tilesheet Matching

## Goal

Make large source grids practical to use without changing the existing fast single-cell workflow. Users must be able to add every grid cell at once, drag a rectangular pending selection, and optionally keep the final tilesheet dimensions synchronized with the Select tool's configured selection grid.

## Interaction Design

### Grid tool

- A left press and release without meaningful pointer movement keeps the existing behavior: add the clicked grid cell to the bucket immediately.
- A left press followed by movement beyond the platform drag threshold starts a pending rectangular selection instead of adding a cell.
- The drag anchor is the cell where the press began. As the pointer crosses grid cells, the pending rectangle expands or contracts to include every cell between the anchor and current cell, inclusive.
- The pending selection is aligned to the current grid origin and tile dimensions. It is shown with the existing blue selection language and internal cell lines.
- Releasing the drag leaves the rectangle selected. It does not add tiles.
- `Add Selection to Bucket` adds the pending Grid-tool cells in row-major order. In Select mode, the same button continues to add the fixed selection matrix.
- Changing tools or moving the grid clears a pending Grid-tool selection because its cell coordinates are no longer reliable.

### Add All

- Add an `Add All` button immediately beside `Add Selection to Bucket`.
- The button is available only when the Grid tool is active, a valid source grid exists, and the bucket has capacity.
- Activating it considers every cell in the current grid in row-major order.
- Cells already represented in the bucket by the same source rectangle are skipped.
- Bulk additions are atomic. If the number of new cells exceeds remaining final-sheet capacity, show a warning stating the required and available slots and add nothing.
- If no new cells remain, leave the bucket unchanged and show an informative status message.

### Contextual settings

- The `Selection grid` property row is visible only while the Select tool is active. It is hidden for Pointer and Grid tools.
- This visibility affects presentation only; the configured selection columns and rows remain stored.
- `Add Selection to Bucket` remains available in Select and Grid modes because both modes can produce a pending selection. Existing behavior outside those modes is unchanged.

### Match selection grid

- Add a `Match selection grid` checkbox on the `Final tilesheet` row beside the final columns and rows.
- When checked, `sheet_columns` equals `selection_columns` and `sheet_rows` equals `selection_rows` immediately and after every subsequent selection-grid edit.
- While checked, the final columns and rows controls are disabled to communicate that they are derived values.
- The checkbox never follows a temporary Grid-tool drag selection. A 5 x 3 drag does not change either configured selection-grid dimensions or final-sheet dimensions.
- When unchecked, final columns and rows retain their current synchronized values and become independently editable.
- Persist the boolean in `AppSettings` and project JSON. Loading older projects without the field defaults it to false.

## Component Responsibilities

### `SourceViewer`

- Own pointer gesture classification, grid drag anchor/current cells, and the pending Grid-tool selection overlay.
- Expose the exact pending grid-cell rectangles in row-major order.
- Expose all current grid-cell rectangles for Add All.
- Continue emitting the existing single-cell signal only for a click, never for a classified drag.
- Clear pending grid selection when the grid becomes invalid, moves, or the active tool changes.

### `SettingsPanel`

- Own the new Add All button, the match checkbox, synchronized spin-box state, and tool-dependent row visibility.
- Emit a dedicated Add All request.
- Include the synchronization boolean and derived dimensions when producing settings.
- Update controls without recursive settings-change signals when loading or synchronizing values.

### `MainWindow`

- Route tool changes to settings visibility.
- Route Add Selection according to the active tool: configured Select matrix versus exact pending Grid rectangles.
- Route Add All to the viewer's complete current grid rectangle list.
- Apply duplicate filtering, capacity validation, tile creation, refresh, selection, and status messages for bulk operations through one shared helper.

### `AppSettings`

- Add `match_sheet_to_selection: bool = False`.
- Preserve backward-compatible loading through the dataclass default when the JSON field is absent.

## Data Flow

1. Grid left press records an anchor cell and press position.
2. Movement past the drag threshold classifies the gesture as a drag and updates an inclusive cell rectangle.
3. Release leaves the pending cell rectangles in `SourceViewer`.
4. Add Selection asks the viewer for those exact rectangles and passes them to the shared bulk-add helper.
5. Add All asks the viewer for every current grid rectangle and uses the same helper.
6. The helper removes rectangles already in the bucket, validates remaining capacity, adds all new tiles, and refreshes the UI once.
7. Settings changes synchronize final dimensions before emitting `AppSettings`, so model capacity and preview always see a consistent state.

## Error and Edge Handling

- A drag beginning outside the valid grid does not create a selection.
- Pointer positions outside the grid clamp the current drag cell to the nearest valid grid cell so dragging toward an edge can still select through that edge.
- Invalid grids leave Add All disabled and expose the existing grid status message.
- A bulk request with no pending Grid selection shows guidance rather than adding anything.
- Duplicate cells do not consume capacity and are not added again.
- Capacity failure is atomic; partial bulk additions are not allowed.
- Existing projects remain loadable and default to independent final-sheet dimensions.

## Verification

- Unit-test drag cell-range normalization in all directions and row-major rectangle output.
- UI-test that a click still emits one grid cell while a drag creates a pending selection without emitting additions.
- UI-test Add Selection for Grid mode, duplicate skipping, atomic capacity failure, and Add All.
- UI-test Selection grid row visibility for Select, Grid, and Pointer tools.
- UI-test checked synchronization, disabled final controls, unchecking behavior, and project-setting round trips.
- Run the full existing test suite and an application import/build smoke check.

## Out of Scope

- Free-form or non-rectangular multi-selection.
- Modifier-key toggling of individual cells.
- Making temporary Grid drag dimensions change the Select tool's configured matrix.
- Changing the established colors, overall layout, or bucket ordering model.

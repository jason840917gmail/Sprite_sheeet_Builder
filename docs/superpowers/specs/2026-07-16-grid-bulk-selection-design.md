# Grid Bulk Selection and Tilesheet Matching

## Goal

Make large source grids practical to use without changing the existing fast single-cell workflow. Users must be able to add every grid cell at once, drag a rectangular pending selection, and optionally keep the final tilesheet dimensions synchronized with the full painted Grid-tool layout calculated from the source image and tile size.

## Interaction Design

### Grid tool

- A left press and release without meaningful pointer movement keeps the existing behavior: add the clicked grid cell to the bucket immediately.
- A left press followed by movement beyond the platform drag threshold starts a pending rectangular selection instead of adding a cell.
- The drag anchor is the cell where the press began. As the pointer crosses grid cells, the pending rectangle expands or contracts to include every cell between the anchor and current cell, inclusive.
- The pending selection is aligned to the current grid origin and tile dimensions. It is shown with the existing blue selection language and internal cell lines.
- Releasing the drag leaves the rectangle selected. It does not add tiles.
- `Add Selection to Bucket` adds the pending Grid-tool cells in row-major order. In Select mode, the same button continues to add the fixed selection matrix.
- A new drag replaces the previous pending Grid-tool selection. A non-drag click clears any previous pending selection before adding its single cell.
- Escape and Clear Selection clear pending selections in both Select and Grid modes.
- A successful pending-selection bulk add clears that selection. A duplicate-only result or failure leaves it selected so the user can correct capacity or settings and retry.
- Changing tools, moving the grid, rebuilding it because its geometry changed, editing tile dimensions, or replacing the source image clears a pending Grid-tool selection because its cell coordinates are no longer reliable.
- Non-geometric settings changes, including final-sheet rows/columns and processing options, do not rebuild grid geometry and preserve a pending selection so a failed capacity check can be corrected and retried.

### Add All

- Add an `Add All` button immediately beside `Add Selection to Bucket`.
- The button is hidden outside Grid mode. In Grid mode it is visible but disabled when the grid is invalid or no bucket capacity remains, and visible and enabled otherwise.
- Activating it considers every cell in the current grid in row-major order.
- Cells already represented in the bucket by the same source rectangle are skipped.
- Bulk additions are atomic. If the number of new cells exceeds remaining final-sheet capacity, show a warning stating the required and available slots and add nothing.
- If no new cells remain, leave the bucket unchanged and show an informative status message.
- `MainWindow` owns a single action-state refresh that passes the active tool, viewer grid validity, tile count, and final-sheet capacity to `SettingsPanel`. It runs after tool changes, image loads, grid/settings rebuilds, grid status changes, and every bucket mutation so Add All cannot retain stale enabled state.

### Contextual settings

- In the right-side Settings panel, the entire `Selection grid` property row (label, columns field, `x`, and rows field) is shown only while the Select tool is active.
- Switching to the Grid or Pointer tool removes that row from view. The Grid tool must not show Selection grid settings because its grid size comes from the source image and tile dimensions, not the Select tool's matrix.
- This visibility affects presentation only; the configured selection columns and rows remain stored.
- `Add Selection to Bucket` remains available in Select and Grid modes because both modes can produce a pending selection. Existing behavior outside those modes is unchanged.

### Match painted grid

- Add a `Match Grid` checkbox on the `Final tilesheet` row beside the final columns and rows.
- When checked, `sheet_columns` and `sheet_rows` equal the complete painted Grid-tool layout's calculated columns and rows. For example, a viewer status of `Ready 19 x 19` produces a `19 x 19` final tilesheet.
- The painted layout is calculated from source-image dimensions and tile dimensions. Loading another source image or changing tile size recalculates the painted grid and updates final dimensions while matching remains checked.
- While checked, the final columns and rows controls are disabled to communicate that they are derived values.
- The checkbox never follows the Select tool's configured `Selection grid` values. A configured `1 x 1` Selection grid does not override a painted `19 x 19` grid.
- The checkbox never follows a temporary Grid-tool drag selection. A 5 x 3 drag does not change final-sheet dimensions.
- When unchecked, final columns and rows retain their current synchronized values and become independently editable.
- Persist the boolean in `AppSettings` and project JSON. Loading older projects without the field defaults it to false.
- Because `AppSettings` does not own source-image dimensions, `MainWindow` owns synchronization. It obtains the calculated dimensions from `SourceViewer`, updates both model settings and panel controls without recursive signals, and refreshes capacity/preview state.
- If matching is checked while no valid painted grid exists, preserve the last valid final dimensions and keep the final controls locked. Synchronize as soon as a valid source image and tile size produce a grid.
- If project JSON says matching is true but contains dimensions that differ from the painted grid, keep the stored values only until the source image loads; then the painted-grid dimensions win.
- Synchronization is allowed to reduce capacity below the current bucket count. Existing tiles are never deleted. The preview continues to show overflow using the existing overflow-tolerant path, additions remain disabled, and export remains unavailable with the existing capacity warning until the user increases capacity or removes tiles.

## Component Responsibilities

### `SourceViewer`

- Own pointer gesture classification, grid drag anchor/current cells, and the pending Grid-tool selection overlay.
- Expose the exact pending grid-cell rectangles in row-major order.
- Expose all current grid-cell rectangles for Add All.
- Expose the calculated painted-grid dimensions as `(columns, rows)` when valid and no value when invalid.
- Continue emitting the existing single-cell signal only for a click, never for a classified drag.
- Clear pending grid selection when the grid becomes invalid, moves, or the active tool changes.
- Rebuild grid geometry only when its inputs (source image, tile dimensions, or grid origin) change; selection-matrix, final-sheet, and image-processing settings must not invalidate a pending Grid selection.

### `SettingsPanel`

- Own the new Add All button, the `Match Grid` checkbox, synchronized spin-box presentation, and tool-dependent row visibility.
- Emit a dedicated Add All request.
- Include the synchronization boolean and currently displayed final dimensions when producing settings.
- Update controls without recursive settings-change signals when loading or synchronizing values.
- Accept current action context from `MainWindow` and derive Add All visibility/enabled state from active tool, grid validity, and remaining capacity.

### `MainWindow`

- Route tool changes to settings visibility.
- Route Add Selection according to the active tool: configured Select matrix versus exact pending Grid rectangles.
- Route Add All to the viewer's complete current grid rectangle list.
- Apply duplicate filtering, capacity validation, atomic tile creation, refresh, selection, and status messages for bulk operations through one shared helper.
- After a successful bulk add, select the last newly added tile. Duplicate-only and failed operations preserve the current bucket selection.
- When matching is enabled, copy `SourceViewer`'s painted-grid dimensions into model settings and panel controls after source-image loads, project loads, checkbox changes, and tile-dimension changes.

### `AppSettings`

- Add `match_sheet_to_grid: bool = False`.
- Preserve backward-compatible loading through the dataclass default when the JSON field is absent.
- Continue validating stored final dimensions but do not derive them from Selection grid; painted-grid derivation requires the viewer/source-image context owned by `MainWindow`.

### `ProjectModel`

- Provide an atomic multi-rectangle add operation. It processes every requested crop into a temporary list, using the names the items will receive, and extends `tiles` only after all processing succeeds.
- If any crop fails, discard the temporary items and leave `tiles` unchanged.

## Data Flow

1. Grid left press records an anchor cell and press position.
2. Movement past the drag threshold classifies the gesture as a drag and updates an inclusive cell rectangle.
3. Release leaves the pending cell rectangles in `SourceViewer`.
4. Add Selection asks the viewer for those exact rectangles and passes them to the shared bulk-add helper.
5. Add All asks the viewer for every current grid rectangle and uses the same helper.
6. The helper removes rectangles already in the bucket before calculating required capacity, validates remaining capacity, asks `ProjectModel` to construct all new tiles atomically, and refreshes the UI once.
7. When matching is checked, `MainWindow` reads the full painted-grid dimensions from `SourceViewer`, writes them to model settings and panel controls, then refreshes capacity and preview state.

## Error and Edge Handling

- A drag beginning outside the valid grid does not create a selection.
- Pointer positions outside the grid clamp the current drag cell to the nearest valid grid cell so dragging toward an edge can still select through that edge.
- Invalid grids leave Add All disabled and expose the existing grid status message.
- A bulk request with no pending Grid selection shows guidance rather than adding anything.
- Duplicate cells do not consume capacity and are not added again.
- Capacity and processing failures are atomic; partial bulk additions are not allowed.
- Existing projects remain loadable and default to independent final-sheet dimensions.
- If matching produces capacity smaller than the existing bucket, keep all tiles and use the existing overflow preview/export safeguards.
- If the painted grid is invalid, keep the last valid matched dimensions and synchronize automatically when it becomes valid again.

## Verification

- Unit-test drag cell-range normalization in all directions and row-major rectangle output.
- UI-test that a click still emits one grid cell while a drag creates a pending selection without emitting additions.
- UI-test Add Selection for Grid mode, duplicate skipping, atomic capacity failure, and Add All.
- UI-test Selection grid row visibility for Select, Grid, and Pointer tools.
- UI-test checked painted-grid synchronization, disabled final controls, unchecking behavior, and project-setting round trips.
- UI-test that a `19 x 19` painted grid produces a `19 x 19` final tilesheet even when Selection grid is `1 x 1`.
- UI-test that tile-size and source-image changes recalculate matched dimensions, while drag-selection and Selection-grid changes do not.
- Unit-test that older project settings default to unmatched and that matching state persists without making `AppSettings` derive from Selection grid.
- Unit-test the shared bulk path's duplicate filtering before capacity calculation, last-added selection result, duplicate-only no-op, and capacity failure with no mutation.
- Unit-test `ProjectModel` atomic multi-add by forcing a later crop to fail and asserting that no tiles or names were committed.
- UI-test Add All action state after tool changes, image/grid validity changes, settings rebuilds, and bucket capacity changes.
- UI-test pending-selection clearing/replacement for click, new drag, Escape, grid/tile changes, image replacement, successful add, duplicate-only result, and failure.
- Run the full existing test suite and an application import/build smoke check.

## Out of Scope

- Free-form or non-rectangular multi-selection.
- Modifier-key toggling of individual cells.
- Making temporary Grid drag dimensions change the Select tool's configured matrix.
- Making the Select tool's configured matrix or a temporary Grid drag determine matched final-sheet dimensions.
- Changing the established colors, overall layout, or bucket ordering model.

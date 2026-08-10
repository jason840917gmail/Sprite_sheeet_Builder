# Bucket Output Resize and Tile Rotation Implementation Plan

## Status

Implemented in the working tree on 2026-08-06. The acceptance suite passes with 166 tests, including independent source/output dimensions, interactive rotation, continuous drag feedback, undo/redo, persistence, and export coverage.

## Outcome

An image selection may remain `256 x 256` while every tile entering the bucket is normalized to a separately configured size such as `64 x 64`. The configured bucket size, not the source selection size, defines final sheet dimensions, individual tile export dimensions, animation frames, and metadata coordinates.

Users can also select a bucket tile, activate a Rotate tool, and rotate it directly in the existing source viewer with visible corner handles, a center rotation ring, a movable pivot, live angle feedback, snapping, Apply/Cancel, and exact undo/redo. Rotation and per-tile resizing always occur inside the project's fixed bucket canvas.

## Locked Product Decisions

1. **Source selection size and bucket/output size are separate settings.** Select and Grid use source selection dimensions. Bucket images and final sheets use bucket/output dimensions.
2. **One project has one uniform bucket canvas size.** A regular spritesheet cannot safely mix cell dimensions. A per-tile resize scales content inside the fixed canvas; it never changes one cell's sheet dimensions.
3. **New tiles normalize on insertion.** The image and video paths share one Fit/Fill/Stretch/No Scale compositor and one resampling policy.
4. **Changing bucket size updates existing tiles atomically.** All existing bucket tiles are re-rendered in one undoable operation so the bucket never enters a mixed-size state.
5. **Rotation is bucket-only.** Source images, source selections, and source Grid cells cannot be rotated by this tool.
6. **Transform editing is staged.** Dragging or typing updates a live preview. Apply/Enter commits one command; Cancel/Escape restores the exact pre-session pixels and metadata.
7. **The canvas remains fixed while rotating.** Content outside the bucket bounds is clipped. The UI warns about clipping and offers Fit Rotated Content.
8. **Alpha correctness is mandatory.** Resize and rotation operate on premultiplied color and alpha, then return straight-alpha RGBA without dark or colored edge halos.
9. **Existing projects remain visually unchanged.** Schema-v2 projects migrate by using the old tile size for both source selection and bucket size and by assigning identity transforms.
10. **Paint Cleanup and transforms have a defined boundary.** Entering bucket Paint with an active transform bakes the displayed result into the editable base and resets the transform before the first stroke. The bake and stroke remain undoable.

## Terminology

| Term | Meaning |
|---|---|
| Source selection size | Width and height of one Select/Grid cell on the original source. |
| Bucket/output size | Fixed transparent canvas used by every bucket tile and final sheet cell. |
| Editable base | Tile pixels before the current per-tile scale and rotation. |
| Tile transform | Per-tile X/Y scale, rotation angle, pivot, and resampling override. |
| Rendered tile | Exact fixed-size RGBA image shown in the bucket and used for export. |

## Target Data Flow

```text
source image/video frame
    -> source crop and background processing
    -> trim/cleanup
    -> add-to-bucket normalization (Fit/Fill/Stretch/No Scale)
    -> editable fixed-size bucket base
    -> per-tile scale and rotation
    -> edge bleed and straight-alpha rendered tile
    -> bucket preview / animation / sheet / exports
```

The final sheet width and height are always:

```text
bucket_tile_width  * sheet_columns
bucket_tile_height * sheet_rows
```

## Settings and Model Shape

### Project settings

Add explicit source and bucket geometry while retaining `AppSettings` as the compatibility facade during this implementation:

```text
selection_tile_width: int
selection_tile_height: int
lock_selection_aspect: bool
bucket_tile_width: int
bucket_tile_height: int
lock_bucket_aspect: bool
bucket_resize_mode: none | fit_down_only | fit | fill | stretch
bucket_resample_mode: nearest | smooth
```

Existing `selection_columns`, `selection_rows`, `padding`, `anchor`, `sheet_columns`, and `sheet_rows` remain. Padding defines the inner placement rectangle for every resize mode. Anchor determines placement when transparent space remains.

Legacy scale modes migrate as follows:

| Schema-v2 value | Schema-v3 bucket mode |
|---|---|
| `none` | `none` |
| `scale_down_only` | `fit_down_only` |
| `scale_to_fit` | `fit` |

### New scoped models

- `BucketSettings`: fixed output geometry, resize mode, resampling, padding, anchor, and edge bleed.
- `TileTransform`: `scale_x`, `scale_y`, `angle_degrees`, normalized `pivot_x`/`pivot_y`, and optional resampling override.

### Tile state

Extend `TileItem` with:

- `base_image_rgba`: editable, untransformed fixed-canvas pixels;
- `transform`: validated `TileTransform`;
- `image_rgba`: rendered fixed-canvas cache used by the current UI and exporters.

`image_rgba` remains available throughout the migration so existing widgets do not need to change at once. Every path that changes the base, transform, or bucket settings must refresh this cache through the shared tile renderer.

## Interaction Specification

### Bucket resize controls

The image Settings panel separates the existing row into:

- **Source selection:** width, linked-dimensions toggle, height.
- **Bucket/output tile:** width, linked-dimensions toggle, height.
- **On Add resize:** Fit, Fit Down Only, Fill/Crop, Stretch, or No Scale.
- **Resampling:** Nearest or Smooth.

Fit is the recommended default for new projects. Schema-v2 projects preserve their migrated mode rather than silently switching.

When bucket dimensions change while tiles exist:

1. Show the proposed old and new dimensions and affected tile count.
2. Apply the new project setting and re-render every tile as one command.
3. Preserve names, ordering, source metadata, edits, and per-tile transforms.
4. Keep the selected bucket row selected.
5. Permit one-step undo/redo of both settings and pixels.

The bucket label displays `crop 256x256 -> output 64x64`. The final preview displays both source selection and bucket/output size so the distinction remains visible.

### Per-tile resize controls

The Tile Transform panel contains:

- linked X/Y scale fields expressed as percentages;
- resulting visible-content size in pixels;
- Reset Scale;
- Fit Content;
- Fill Canvas;
- rotation controls described below.

Scale changes are staged in the same transform session as rotation. This allows several scale and rotation adjustments to be committed in one raster render and one undo step.

### Rotate tool

Add a toolbar/menu action named **Rotate**, shortcut `R`.

- The action is disabled when the bucket is empty.
- Activating it previews the selected bucket tile; if no row is selected, it selects the first tile.
- Clicking another bucket row switches the transform target after resolving any staged changes.
- Leaving Rotate with unapplied changes requests Apply, Discard, or Cancel tool switch.
- The normal source image is restored when Rotate exits.

The on-canvas overlay contains:

- four screen-size-stable corner rotation handles;
- a center rotation ring that may also be dragged to rotate;
- a smaller center pivot dot that may be dragged independently;
- a dashed transformed-content outline;
- fixed bucket-canvas boundary;
- a small angle readout during dragging;
- a visible clipping warning when transformed content crosses the canvas boundary.

Behavior:

- Corner or center-ring drag rotates freely around the pivot.
- Shift snaps to 15-degree increments.
- The panel accepts a numeric angle for precise rotation.
- Quick actions provide `-90`, `+90`, `180`, Reset Angle, and Center Pivot.
- Enter or Apply commits.
- Escape or Cancel discards staged changes. Escape outside an active transform session keeps its existing selection/preview behavior.
- Fit Rotated Content reduces scale just enough to fit the transformed bounds inside the bucket canvas.

## Milestones

| Milestone | Tasks | Exit condition |
|---|---:|---|
| A. Separate geometry | 1-3 | A `256 x 256` source selection can produce a correct `64 x 64` bucket tile and sheet cell. |
| B. Reliable transforms | 4-5 | Per-tile scale/rotation render correctly with alpha-safe output and undoable state. |
| C. Editor interaction | 6-7 | Bucket-only handles, pivot, live preview, snapping, Apply/Cancel, and tool switching work. |
| D. Persistence and release | 8-10 | Schema migration, exact reload/export, help, performance, and complete regression gates pass. |

## Task 1: Lock the baseline and add failing geometry tests

### Files

- Modify `sprite_sheet_cleaner/tests/test_settings_models.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_model.py`.
- Modify `sprite_sheet_cleaner/tests/test_sheet_builder.py`.
- Modify `sprite_sheet_cleaner/tests/test_export_manager.py`.
- Modify `sprite_sheet_cleaner/tests/test_main_window.py`.

### Work

1. Record the current full-suite result before changing production code.
2. Add a failing model test proving a `256 x 256` crop can produce a `64 x 64` bucket image.
3. Add a failing sheet test proving `8 x 8` cells at `64 x 64` produce a `512 x 512` sheet regardless of source selection dimensions.
4. Add failing export metadata assertions that sheet rectangles use bucket/output dimensions.
5. Add a UI test proving editing source selection size does not change bucket/output fields and vice versa.
6. Preserve existing tests for Match Grid, selection grids, capacity, video metadata, alpha, and output ordering.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner/tests/test_settings_models.py sprite_sheet_cleaner/tests/test_project_model.py sprite_sheet_cleaner/tests/test_sheet_builder.py sprite_sheet_cleaner/tests/test_export_manager.py sprite_sheet_cleaner/tests/test_main_window.py -q
```

### Commit

`test: define separate selection and bucket geometry`

## Task 2: Introduce bucket settings and schema-v3 migration

### Files

- Create `sprite_sheet_cleaner/app/models/bucket_settings.py`.
- Create `sprite_sheet_cleaner/app/models/tile_transform.py`.
- Create `sprite_sheet_cleaner/app/storage/project_migrations.py`.
- Modify `sprite_sheet_cleaner/app/models/app_settings.py`.
- Modify `sprite_sheet_cleaner/app/models/tile_settings.py`.
- Modify `sprite_sheet_cleaner/app/models/sheet_settings.py`.
- Modify `sprite_sheet_cleaner/app/models/tile_item.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_schema.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_archive.py`.
- Modify `sprite_sheet_cleaner/tests/test_settings_models.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_archive.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_model.py`.

### Work

1. Add validated bucket and transform dataclasses with finite-number, positive-size, pivot, scale, angle, mode, and resampling checks.
2. Add explicit source-selection and bucket fields to the compatibility settings facade.
3. Increment the project schema to 3 and permit safe migration from schema 2.
4. Migrate old tile width/height to both new geometry domains.
5. Migrate existing scale modes without changing old project appearance.
6. Treat every schema-v2 tile PNG as its editable base with an identity transform.
7. Reject unknown transform versions, non-finite angles/scales, invalid pivots, invalid dimensions, and unsupported resize modes.
8. Keep archive entry validation and pixel-count limits effective for the new representation.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner/tests/test_settings_models.py sprite_sheet_cleaner/tests/test_project_archive.py sprite_sheet_cleaner/tests/test_project_model.py -q
```

### Commit

`feat: separate bucket settings and migrate project schema`

## Task 3: Build the shared bucket compositor

### Files

- Create `sprite_sheet_cleaner/app/core/bucket_renderer.py`.
- Create `sprite_sheet_cleaner/tests/test_bucket_renderer.py`.
- Modify `sprite_sheet_cleaner/app/core/alpha_ops.py`.
- Modify `sprite_sheet_cleaner/app/core/frame_resizer.py`.
- Modify `sprite_sheet_cleaner/app/core/image_processor.py`.
- Modify `sprite_sheet_cleaner/tests/test_alpha_ops.py`.
- Modify `sprite_sheet_cleaner/tests/test_frame_resizer.py`.
- Modify `sprite_sheet_cleaner/tests/test_image_processor.py`.

### Work

1. Extract one reusable compositor for image selections and video frames.
2. Implement No Scale, Fit Down Only, Fit, Fill/Crop, and Stretch against the padded inner canvas.
3. Honor center and bottom-center anchors when transparent space remains.
4. Support Nearest and Smooth resampling. Smooth uses the current premultiplied-alpha path; Nearest must preserve exact palette-like RGBA values.
5. Return an exact bucket-sized RGBA base for every successful input.
6. Apply edge bleed only after the final rendered transform, never between intermediate renders.
7. Keep transparent pixels, semitransparent edges, hidden RGB, and one-pixel artwork correct.
8. Replace duplicated video-specific resize behavior with the shared primitive while retaining `FrameResizeSettings` as a compatibility adapter.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner/tests/test_bucket_renderer.py sprite_sheet_cleaner/tests/test_alpha_ops.py sprite_sheet_cleaner/tests/test_frame_resizer.py sprite_sheet_cleaner/tests/test_image_processor.py -q
```

### Commit

`feat: add shared alpha safe bucket compositor`

## Task 4: Route insertion, sheets, previews, and exports through bucket size

### Files

- Modify `sprite_sheet_cleaner/app/core/project_model.py`.
- Modify `sprite_sheet_cleaner/app/core/sheet_builder.py`.
- Modify `sprite_sheet_cleaner/app/core/export_manager.py`.
- Modify `sprite_sheet_cleaner/app/widgets/final_preview.py`.
- Modify `sprite_sheet_cleaner/app/widgets/bucket_panel.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_model.py`.
- Modify `sprite_sheet_cleaner/tests/test_sheet_builder.py`.
- Modify `sprite_sheet_cleaner/tests/test_export_manager.py`.
- Modify `sprite_sheet_cleaner/tests/test_main_window.py`.

### Work

1. Keep Select and Grid calculations on source selection dimensions.
2. Normalize image selections, grid cells, processed candidates, and video frames to bucket size as they enter the bucket.
3. Make `final_size` equal the rendered bucket dimensions for every new or re-rendered tile.
4. Calculate sheet dimensions and cell placement exclusively from bucket width/height.
5. Validate that every rendered tile matches the configured bucket canvas before sheet export; fail with a useful message instead of silently clipping a malformed tile.
6. Make individual tile export dimensions match the bucket canvas.
7. Make metadata `sheet_rect` and sheet-level tile dimensions use bucket geometry while leaving `source_rect` unchanged.
8. Update bucket and final-preview labels to show the source/output distinction.
9. Preserve capacity behavior: capacity remains rows multiplied by columns and is unrelated to pixel dimensions.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner/tests/test_project_model.py sprite_sheet_cleaner/tests/test_sheet_builder.py sprite_sheet_cleaner/tests/test_export_manager.py sprite_sheet_cleaner/tests/test_main_window.py -q
```

### Commit

`feat: use bucket dimensions for insertion and export`

## Task 5: Add settings UI and undoable existing-bucket resize

### Files

- Modify `sprite_sheet_cleaner/app/widgets/settings_panel.py`.
- Modify `sprite_sheet_cleaner/app/widgets/video_settings_panel.py`.
- Modify `sprite_sheet_cleaner/app/commands/bucket_commands.py`.
- Modify `sprite_sheet_cleaner/app/commands/command_stack.py` only if command composition is required.
- Modify `sprite_sheet_cleaner/app/main_window.py`.
- Modify `sprite_sheet_cleaner/tests/test_settings_panel.py`.
- Modify `sprite_sheet_cleaner/tests/test_paint_controls.py`.
- Modify `sprite_sheet_cleaner/tests/test_command_stack.py`.
- Modify `sprite_sheet_cleaner/tests/test_main_window.py`.

### Work

1. Add separate Source Selection and Bucket/Output rows with independent linked-dimension toggles.
2. Add resize-mode and resampling controls with concise tooltips and accessible names.
3. Treat bucket geometry changes as explicit commands containing before/after settings and tile snapshots.
4. Re-render all existing tiles atomically and roll back settings and pixels if any tile fails.
5. Preserve bucket selection, scroll position where practical, names, ordering, source/video metadata, and stable tile IDs.
6. Share bucket/output dimensions across image and video modes. Relabel video frame size if necessary so it is clear whether it controls pre-bucket framing or the shared output canvas.
7. Ensure unrelated settings such as sheet rows, tolerance, and source selection size do not resize existing bucket pixels.
8. Confirm Paint Cleanup still targets the selected rendered tile.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner/tests/test_settings_panel.py sprite_sheet_cleaner/tests/test_paint_controls.py sprite_sheet_cleaner/tests/test_command_stack.py sprite_sheet_cleaner/tests/test_main_window.py -q
```

### Commit

`feat: add bucket size controls and undoable resize`

## Task 6: Implement deterministic per-tile transform rendering

### Files

- Create `sprite_sheet_cleaner/app/core/tile_transform.py`.
- Create `sprite_sheet_cleaner/tests/test_tile_transform.py`.
- Modify `sprite_sheet_cleaner/app/core/alpha_ops.py`.
- Modify `sprite_sheet_cleaner/app/models/tile_item.py`.
- Modify `sprite_sheet_cleaner/app/commands/bucket_commands.py`.
- Modify `sprite_sheet_cleaner/app/core/project_model.py`.
- Modify `sprite_sheet_cleaner/tests/test_alpha_ops.py`.
- Modify `sprite_sheet_cleaner/tests/test_command_stack.py`.

### Work

1. Implement angle normalization, shortest-angle deltas, pivot mapping, scale matrices, transformed bounds, and 15-degree snapping as pure tested helpers.
2. Rotate premultiplied RGB and alpha with `expand=False` onto the fixed bucket canvas, then safely return straight-alpha RGBA.
3. Render every staged preview from one unchanged editable base and the complete current transform; never rotate the preceding preview frame.
4. Implement nearest and smooth transform sampling.
5. Detect whether visible transformed bounds exceed the bucket canvas.
6. Implement Fit Rotated Content by solving the maximum uniform scale that keeps the transformed visible bounds inside the padded canvas.
7. Copy base pixels and transform state through clone, duplicate, bucket snapshots, undo, and redo.
8. Add exact tests for identity, 90/180-degree rotations, off-center pivots, transparent edges, clipping, snapping across `-180/180`, reset, and repeated preview stability.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner/tests/test_tile_transform.py sprite_sheet_cleaner/tests/test_alpha_ops.py sprite_sheet_cleaner/tests/test_command_stack.py -q
```

### Commit

`feat: add deterministic bucket tile transforms`

## Task 7: Add the Rotate overlay and transform panel

### Files

- Create `sprite_sheet_cleaner/app/widgets/tile_transform_panel.py`.
- Create `sprite_sheet_cleaner/app/widgets/tile_transform_overlay.py` if separating graphics-item concerns keeps `SourceViewer` manageable.
- Create `sprite_sheet_cleaner/tests/test_tile_transform_panel.py`.
- Create `sprite_sheet_cleaner/tests/test_tile_transform_overlay.py`.
- Modify `sprite_sheet_cleaner/app/widgets/source_viewer.py`.
- Modify `sprite_sheet_cleaner/app/utils/tool_icons.py`.
- Modify `sprite_sheet_cleaner/tests/test_source_viewer.py`.

### Work

1. Add `rotate` to the viewer tool type and give it its own cursor/hint text.
2. Draw the transformed-content outline, four corner handles, center rotation ring, pivot dot, fixed canvas boundary, live angle, and clipping warning above the tile pixmap.
3. Keep handles a stable screen size across zoom levels and use viewport-space hit radii for reliable mouse targeting.
4. Add pure hit-test states: none, corner rotation, center-ring rotation, and pivot move.
5. Emit staged transform requests rather than mutating `TileItem` directly from the viewer.
6. Add Shift snapping during rotation and clamp the pivot to a documented safe range while permitting it to move outside visible content but inside the tile canvas.
7. Build panel controls for linked scale, angle, quick rotations, reset actions, center pivot, Fit Content, Fill Canvas, Fit Rotated Content, resampling override, Apply, and Cancel.
8. Ensure overlay items never appear for source images, Select, Grid, Pointer, or Paint.
9. Add keyboard and accessibility labels for every action.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner/tests/test_tile_transform_panel.py sprite_sheet_cleaner/tests/test_tile_transform_overlay.py sprite_sheet_cleaner/tests/test_source_viewer.py -q
```

### Commit

`feat: add interactive bucket rotate controls`

## Task 8: Integrate transform sessions with bucket preview and Paint

### Files

- Modify `sprite_sheet_cleaner/app/main_window.py`.
- Modify `sprite_sheet_cleaner/app/widgets/bucket_panel.py`.
- Modify `sprite_sheet_cleaner/app/widgets/retouch_panel.py` only if status text needs expansion.
- Modify `sprite_sheet_cleaner/app/core/retouch.py` only if the bake seam needs a helper.
- Modify `sprite_sheet_cleaner/tests/test_main_window.py`.
- Modify `sprite_sheet_cleaner/tests/test_retouch.py`.
- Modify `sprite_sheet_cleaner/tests/test_paint_controls.py`.

### Work

1. Add the Rotate action to the toolbar, Tools menu, exclusive tool group, shortcut, and status text.
2. Track one transform session containing target tile ID/index, exact before snapshot, editable working transform, and dirty state.
3. Activate Rotate by selecting/previewing a bucket tile; disable it when the bucket is empty.
4. Route viewer drag signals and panel edits into live rendering without adding commands during movement.
5. Commit the complete session as one bucket command on Apply/Enter.
6. Restore the exact before snapshot on Cancel/Escape.
7. Define target-switch behavior: clean sessions switch immediately; dirty sessions request Apply, Discard, or Cancel switch.
8. Restore the normal source/candidate view and existing panel when Rotate exits.
9. Before bucket Paint begins, bake a committed transform into `base_image_rgba`, reset the transform, and include that state in undo. Never silently bake a dirty/unapplied transform session.
10. Restore source preview before delete, clear, duplicate, reorder, project load, source replacement, undo, or redo when those operations invalidate the current transform target.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner/tests/test_main_window.py sprite_sheet_cleaner/tests/test_retouch.py sprite_sheet_cleaner/tests/test_paint_controls.py sprite_sheet_cleaner/tests/test_command_stack.py -q
```

### Commit

`feat: integrate bucket transform sessions`

## Task 9: Persist editable transforms and preserve exact project behavior

### Files

- Modify `sprite_sheet_cleaner/app/core/project_model.py`.
- Modify `sprite_sheet_cleaner/app/services/project_service.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_archive.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_schema.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_migrations.py`.
- Modify `sprite_sheet_cleaner/app/services/legacy_project_importer.py` only if it emits current project data.
- Modify `sprite_sheet_cleaner/tests/test_project_model.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_archive.py`.
- Modify `sprite_sheet_cleaner/tests/test_legacy_project_importer.py`.
- Modify `sprite_sheet_cleaner/tests/test_export_manager.py`.

### Work

1. Save the editable base PNG at the existing safe tile asset path and store transform metadata in `project.json`.
2. Store a transform recipe version and bucket render settings needed for deterministic reload.
3. Render `image_rgba` from base plus transform on load; do not double-apply schema-v2 rendered snapshots.
4. Preserve image/video source type, source paths, frame indexes, timestamps, resize metadata, revision IDs, stable tile IDs, and transform metadata when project-service tile records are rebuilt.
5. Add exact pixel round-trip tests for identity, scale, rotation, pivot, nearest, smooth, and painted-then-baked tiles.
6. Prove a schema-v2 project opens with identical output dimensions and pixels and then saves as schema 3.
7. Prove malformed transform data is rejected before model mutation.
8. Ensure rendered exports after reload match rendered exports before save.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner/tests/test_project_model.py sprite_sheet_cleaner/tests/test_project_archive.py sprite_sheet_cleaner/tests/test_legacy_project_importer.py sprite_sheet_cleaner/tests/test_export_manager.py -q
```

### Commit

`feat: persist editable bucket transforms`

## Task 10: Complete documentation, performance, and release gates

### Files

- Modify `help/getting-started.md`.
- Modify `help/right-panel.md`.
- Modify `help/keyboard-shortcuts.md`.
- Modify `help/index.json` if a new page is added.
- Create `help/bucket-transforms.md` if the existing pages become crowded.
- Modify root `README.md`.
- Modify `sprite_sheet_cleaner/README.md`.
- Modify `Plan/BuildStatus.md`.
- Modify or create focused performance tests only where repeatable in CI.

### Work

1. Document the source-selection versus bucket/output distinction with the `256 -> 64` example.
2. Document every add resize mode, resampling choice, clipping rule, pivot behavior, modifier, quick action, Apply/Cancel, and Paint bake behavior.
3. Run the complete test suite with PySide6 and zero new unexpected skips.
4. Run compile and formatting/diff checks.
5. Manually inspect nearest and smooth results at 100%, high zoom, and animation playback.
6. Test wide, tall, square, one-pixel, semitransparent, trimmed, bottom-anchored, and fully transparent sprites.
7. Verify live transform interaction remains responsive on `4096 x 4096` bucket canvases. If full-quality preview exceeds the UI latency budget, use a temporary scaled preview during drag and always render full quality on Apply.
8. Verify final sheets and individual PNGs on checkerboard, black, white, and colored backgrounds.
9. Confirm old image projects, old video projects, multi-video projects, source candidates, Paint Cleanup, Grid Add All, animation preview, exports, and undo/redo still work.
10. Update Build Status with exact test counts, manual results, limitations, and any deferred follow-ups.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner/tests -q
python -m compileall -q sprite_sheet_cleaner
git diff --check
git status --short
```

### Commit

`docs: complete bucket resize and rotation release gates`

## Final Acceptance Checklist

- [x] Source selection dimensions and bucket/output dimensions are independent.
- [x] A `256 x 256` source selection can add an exact `64 x 64` bucket tile.
- [x] Fit, Fit Down Only, Fill/Crop, Stretch, and No Scale behave as documented.
- [x] Nearest preserves pixel-art edges; Smooth preserves alpha without halos.
- [x] Existing bucket tiles resize atomically when bucket dimensions change.
- [x] Bucket resizing is undoable and restores both settings and exact pixels.
- [x] Final preview, animation, sheets, individual exports, and metadata use bucket dimensions.
- [x] Per-tile scaling stays inside the fixed bucket canvas.
- [x] Rotate is disabled for empty buckets and unavailable for source content.
- [x] Rotate displays corner handles, center ring, pivot, outline, angle, canvas boundary, and clipping state.
- [x] Shift rotation snaps to 15-degree increments.
- [x] Numeric angle, quick rotations, reset, center pivot, and Fit Rotated Content work.
- [x] Apply commits one undoable transform; Cancel restores exact prior pixels and metadata.
- [x] Repeated live previews do not compound raster blur.
- [x] Paint bakes a committed transform predictably and remains undoable.
- [x] Duplicate, reorder, delete, clear, undo, and redo preserve valid transform state.
- [x] Schema-v2 projects migrate without visual or dimension changes.
- [x] Schema-v3 projects reload editable transforms and reproduce exact rendered exports.
- [x] Image, video, multi-video, source-background, Grid, Paint, animation, save/load, and export regressions pass.

## Deferred Ideas

These are useful follow-ups but are not required for the first implementation:

- Move content inside the bucket canvas with direct on-canvas dragging.
- Arbitrary transform-bound rotation independent from content rotation.
- Flip horizontal/vertical.
- Multi-select transforms across several bucket tiles.
- Per-animation transform presets.
- A non-destructive inverse-mapped Paint mode that edits through an unbaked transform.
- Multiple bucket/output size profiles in one project; this would require separate sheets rather than mixed cells in one atlas.

## Recommended Implementation Branching

Use an integration branch such as `codex/bucket-resize-rotate`. Review after Milestone A before beginning graphics interaction, because source/output separation and schema migration are the foundation for every later transform. Review again after Milestone C with a manual handle/pivot usability pass before final persistence and release hardening.

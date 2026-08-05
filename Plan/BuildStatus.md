# Sprite Sheet Cleaner Build Status

Updated: 2026-08-05

## Built

- Added the first video-to-spritesheet implementation slice:
  - Open Video action for common video formats.
  - OpenCV-backed video metadata and frame decoding adapter.
  - Configurable start/end frame, sampling interval, and max-frame extraction.
  - Asynchronous frame thumbnail browser with cancellation and stale-worker protection.
  - Multi-select candidate frames and preview the active frame in the existing Source Viewer.
  - Apply the existing crop/background-removal/normalization pipeline to selected video frames.
  - Store source frame index/timestamp metadata on bucket tiles.
  - Larger modal animation preview with playback controls and frame counter.
  - Video animation preview is scoped to the selected frames in the active video tab, so one bucket can hold multiple animations.
  - JSON frame metadata export.
  - Dedicated Video Tool settings panel separate from image/Grid settings.
  - Video frame output sizing with Fit, Stretch, or Fill/Crop applied as frames enter the bucket.
  - Seed Animation action with a user-configurable count, defaulting to 10 distributed random frames.
  - Bucket drag-and-drop reordering for animation cleanup.
  - Per-frame resize metadata persisted and reapplied during reprocessing.
  - Left-click frame thumbnails adds that frame to the bucket; right-click deselects and removes it.
  - Versioned video-aware project data fields with backward-compatible image loading.
  - Multiple videos can be open at once, with one independent frame-browser tab per video.
  - A shared bucket and final tilesheet can combine frames from different video tabs.
  - Each tab keeps its own extraction settings, thumbnail cache, current frame, and selections.
  - Multi-video project save/load restores video tabs and resolves each tile against its original video source.

- Created Python package structure under `sprite_sheet_cleaner/`.
- Added core dataclasses:
  - `AppSettings`
  - `TileItem`
- Added image-processing pipeline:
  - crop source image
  - remove solid RGB background with tolerance
  - trim transparent edges
  - scale by mode
  - place result on a fixed transparent tile canvas
- Added final sheet builder:
  - calculates output dimensions
  - enforces grid capacity by default
  - pastes tiles in row-major grid order
- Added project model:
  - add tiles from crop rectangles
  - remove, duplicate, rename, and move tiles
  - reprocess existing tiles when settings change
  - serialize/load project metadata
- Added export helpers:
  - export final PNG sheet
  - export individual PNG tiles
- Added PySide6 desktop UI code:
  - main window
  - File menu with open, save project, load project, export sheet, export tiles, exit
  - View menu with zoom controls
  - source image viewer with zoom, pan, mouse coordinates, and crop rectangle selection
  - settings panel for tile size, grid, background removal, color, tolerance, trimming, scale mode, padding, and anchor
  - bucket panel with thumbnails plus rename, duplicate, move up/down, and delete
  - final sheet preview with dimensions, capacity, used tiles, empty slots, and overflow count
- Added README with install, run, workflow, Godot import notes, limitations, and roadmap.
- Added unit tests for image processing and sheet building.
- Added `requirements.txt` and PyInstaller build script.
- Added `.gitignore` for Python caches, virtual environments, build outputs, and exports.
- Added root `run_app.py` launcher to avoid package-resolution confusion.
- Enlarged the source viewer startup layout so it is the primary work area, with final preview and side panels as secondary regions.
- Changed source selection to fixed tile-size placement instead of freeform crop drawing.
- Added a Select-mode command overlay in the source work area:
  - left click places the selection
  - arrow keys nudge the selection one pixel at a time
  - `A` adds the selection to the bucket
  - `Esc` clears the selection
- Added selection clearing when switching from Select to Pointer or Grid.
- Added left toolbar tools:
  - Pointer mode for left-drag panning.
  - Select mode for placing the fixed-size tile box.
- Added source-viewer pixel rulers for X/Y image coordinates.
- Changed default processing settings toward no size transformation: no trim, no scaling, and zero padding.
- Moved pixel rulers into reserved top/left gutters so they no longer overlap the image canvas.
- Added pasteboard space around the source image so pointer-drag can move the sheet away from the edges.
- Added background color detection from the current selection border, with image-border fallback.
- Added a bucket capacity counter showing used tiles versus final grid capacity.
- Prevented adding or duplicating tiles once the bucket reaches final sprite sheet capacity.
- Added a `Sym` toggle to link tile width and height in the selection settings.
- Tightened the right-side utility panel and compacted controls so the source canvas remains the main focus.
- Moved the symmetry toggle directly between the width and height tile inputs.
- Added a Grid source-viewer tool:
  - divides the source image by the current tile width and height
  - rounds down when the image dimensions are uneven, leaving right/bottom leftover pixels outside the clickable grid
  - draws an aligned fitted grid overlay
  - draws a high-contrast fitted-grid outline when Grid mode is active
  - lets the user right-click and hold to drag the fitted grid within the image boundaries
  - advises the user that left click selects a tile and right-click drag moves the grid
  - shows those Grid commands as a small top-right overlay inside the source work area
  - reports ready/error grid status in the status bar
  - warns when Grid mode cannot draw because tile size and source image dimensions are incompatible
  - highlights hovered grid cells
  - marks grid cells that are already in the bucket
  - adds clicked grid cells to the bucket through the existing crop-processing pipeline
  - prevents duplicate grid-cell adds by selecting the existing bucket item instead
- Added unit-tested grid geometry helpers for grid calculation, cell lookup, and cell rectangles.
- Added Selection grid settings for the image/Grid workflow:
  - defaults to `1 x 1` so the existing one-tile Select workflow remains unchanged
  - expands the Select overlay by tile columns and rows, such as `1 x 2`
  - adds each selected grid cell to the bucket as its own tile
  - keeps the source Grid tool based on individual tile size
- Moved final output row/column controls below Add Selection and labeled them as Final tilesheet.

## Verified

- `python -m unittest discover -s sprite_sheet_cleaner\tests`
  - Passed: 116 tests; 19 Qt tests skipped because PySide6 is not installed in the current runtime.
- `python -m compileall -q sprite_sheet_cleaner`
  - Passed
- `.venv` offscreen Qt layout smoke test
  - Passed: default source canvas is about 882x606 in a 1320x820 window while the right panel stays near 310px wide.
- `.venv` offscreen Qt tool smoke test
  - Passed: default tool is Select and fixed-size selection placement is available.
- `.venv` offscreen Qt ruler/pasteboard smoke test
  - Passed: viewport begins after ruler gutters and scene includes movable pasteboard space.
- `.venv` offscreen Qt bucket capacity smoke test
  - Passed: full bucket shows `Bucket 1 / 1 (full)` and disables Add/Duplicate.
- `.venv` offscreen Qt linked tile-size smoke test
  - Passed: width and height stay in sync when `Sym` is enabled.
- `.venv` offscreen Qt grid smoke test
  - Passed: Grid tool activates on a 512x512 source image, adds a 256x256 grid cell, and ignores a duplicate click on the same cell.
- `.venv` offscreen Qt uneven grid smoke test
  - Passed: Grid tool activates on a 1000x768 source image with 256x256 tiles, draws a 3x3 fitted grid, and leaves 232px outside the clickable right edge.
- `.venv` offscreen Qt movable grid smoke test
  - Passed: Grid origin clamps inside a 1000x770 source image, moves to X 232 / Y 2, and adds a tile from the shifted origin.
- `.venv` offscreen Qt grid hint overlay smoke test
  - Passed: Grid command hint is hidden in Select mode, appears in Grid mode, and stays inside the source viewer viewport.
- `.venv` offscreen Qt select hint and clear-selection smoke test
  - Passed: Select command hint appears in Select mode, Escape clear path removes the selection, and switching to Pointer/Grid clears the selection.
- `.venv` offscreen Qt select arrow nudge smoke test
  - Passed: Select arrow keys move the selection by 1px and clamp the selection inside the source image.
- `.venv` offscreen Qt selection-grid smoke test
  - Passed: `1 x 2` Select placement adds two tile-sized bucket items.
- `.venv\Scripts\python.exe -m unittest discover -s sprite_sheet_cleaner\tests`
  - Passed: 21 tests
- `.venv\Scripts\python.exe -m compileall -q sprite_sheet_cleaner`
  - Passed
- `python -m sprite_sheet_cleaner.app.main`
  - Requires launching from the workspace root, not from the nested package folder.

## Pending

- Install runtime dependencies from `sprite_sheet_cleaner/requirements.txt`.
- Verify video extraction with real MP4/MOV/WebM files after OpenCV is installed.
- Verify resize modes visually with wide, tall, transparent, and already-square frames.
- Run the new video and export tests in an environment with Python dependencies available.
- Launch and manually verify the PySide6 desktop UI.
- Add visual polish:
  - checkerboard transparency background
  - better empty states
  - richer keyboard shortcuts
  - recent files
- Improve project save/load:
  - warn when source videos moved
  - offer a relink flow when a source is unavailable
  - store per-tile settings if future versions need mixed settings
- Add snap-to-size selection.
- Add richer grid interactions:
  - shift-click or drag to add multiple grid cells
  - auto-fill bucket from all grid cells
- Package with PyInstaller after UI verification.

## Source-background architecture implementation

- Corrected repeated-alpha loss during tile and sheet placement.
- Added premultiplied-alpha scaling and hidden-RGB edge bleed for game-safe
  straight-alpha PNG output.
- Added immutable original sources, candidate/active revisions, one-pass
  Exact Key and Smart Solid engines, cancellable Qt jobs, and explicit
  activation/discard workflow.
- Added **Apply Candidate to Bucket**, which updates existing bucket snapshots
  in one undoable operation without changing the active source revision.
- Added stable tile snapshots, portable `.sscproj` archives, archive limits,
  atomic saves, legacy JSON import, and session undo/redo for bucket updates.
- Added verified optional runtime manifests and a Model Manager for rembg/U2Net
  and BEN2 Base ONNX. Weights live in user data and are verified by SHA-256;
  the repository contains no model files.
- Added an isolated JSON-line AI worker, ONNX provider discovery, NVIDIA
  capability probing, CUDA warm-up, and visible Auto CPU fallback.
- Added atomic export validation, cache indexing/protected entries, sanitized
  diagnostics, and stable error categories.

## Verification (2026-08-05)

- Bundled Python: `116` unit tests passed, `19` expected Qt tests skipped because
  the bundled runtime does not include PySide6.
- `python -m compileall -q sprite_sheet_cleaner`: passed.
- `git diff --check`: passed.

## Remaining release gates

- Run the Qt suite in a supported environment with PySide6 installed.
- On an NVIDIA machine, install both optional runtimes through Model Manager,
  verify the real provider/session warm-up, and measure RAM/VRAM and quality on
  the project corpus.
- Run the offline inference, cancellation, OOM fallback, legacy migration, and
  large-source benchmark gates before packaging.

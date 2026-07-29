# Video-to-Spritesheet Feature Plan

Created: 2026-07-28

## Goal

Add a video workflow that turns selected video frames into a game-ready, fixed-size PNG sprite sheet:

```text
open video
  -> choose frame range and sampling
  -> inspect thumbnails
  -> select frames
  -> optionally crop a shared region
  -> remove background and normalize each frame
  -> preview the animation and final sheet
  -> export PNG plus optional frame metadata
```

The existing image workflow must continue to work unchanged. Video frames should reuse the current processing pipeline wherever possible instead of introducing a second kind of tile processing.

## Current app seams to reuse

- `MainWindow` currently owns one `source_image` and routes image loading, settings changes, bucket updates, and exports.
- `SourceViewer` already supports zoom, pan, fixed-size Select mode, Grid mode, cursor coordinates, and selection rectangles.
- `ProjectModel.add_tile_from_crop()` and `add_tiles_from_rects()` already apply the shared `process_crop()` pipeline.
- `image_processor.py` already handles RGBA conversion, solid-color removal, tolerance, transparent trimming, scaling, padding, anchoring, and fixed tile canvases.
- `TileItem` already stores the processed image, source rectangle, source size, and final size.
- `sheet_builder.py` already assembles bucket tiles in row-major order and enforces sheet capacity.
- `FinalPreview` already reports output dimensions, used slots, empty slots, and overflow.

The main architectural gap is that the current model assumes a single image can provide every source crop. Video support needs a frame source abstraction and frame identity metadata.

## Product decisions

### 1. Keep one bucket and one export pipeline

An image crop and a video frame are both normalized into `TileItem` objects. The bucket remains the single source of truth for ordering and sheet assembly.

For a video frame, use the full frame as the default source rectangle. If the user places a Select rectangle, offer a clear `Apply crop to selected frames` action so the same crop is applied consistently across the sequence.

### 2. Decode lazily and off the UI thread

Do not load an entire video or all full-size frames into memory. Extract thumbnails and full frames on demand, with a bounded in-memory cache.

Use an adapter around OpenCV's `VideoCapture` for the first implementation because it fits the existing Python/Pillow/NumPy stack and supports common desktop video formats. Keep the UI dependent on a small `FrameSource` interface so the decoder can be replaced by PyAV later if codec support or packaged-app reliability requires it.

All extraction work must run through `QThreadPool`/`QRunnable` or an equivalent Qt worker. The worker needs progress, cancellation, and an error signal so large videos never freeze the window.

### 3. Use one stable background setting for a sequence

For video, automatically detecting a different background color for every frame can cause visible alpha flicker. The default should be:

- detect/sample the background from the currently previewed frame's border;
- use that color and tolerance for every selected frame;
- let the user re-sample from another frame when needed.

Add an optional edge-connected removal mode for backgrounds that contain a similar color inside the character. Global color removal remains the simple/default mode for chroma-key-style footage.

### 4. Preserve source order by default

Selected frames should be added to the bucket in ascending source-frame order, regardless of the order in which the user clicks them. The bucket can still be manually reordered afterward.

Skip duplicate frame indices automatically and report how many duplicates were ignored.

### 5. Provide an animation preview before export

A sheet can look correct while the animation timing or frame selection is wrong. Keep the sheet preview inline, but open animation playback in a larger modal preview with configurable FPS, loop, and a frame counter.

## Data model changes

### New `app/core/video_source.py`

Define a decoder-independent source API and implementation:

```python
@dataclass(frozen=True, slots=True)
class VideoMetadata:
    path: str
    width: int
    height: int
    frame_count: int
    fps: float
    duration_seconds: float

@dataclass(frozen=True, slots=True)
class FrameRef:
    index: int
    timestamp_ms: int

class FrameSource:
    def metadata(self) -> VideoMetadata: ...
    def read_frame(self, index: int) -> Image.Image: ...
    def iter_frames(self, refs: list[FrameRef], cancel_token) -> ...: ...
    def close(self) -> None: ...
```

Implement sequential decoding for extraction when possible. Random access should be used for preview only, since codec seeking can land on a nearby keyframe.

Add helpers for deterministic selection:

- frame range from start/end frame or start/end time;
- every-Nth-frame sampling;
- target-FPS sampling;
- maximum frame count validation;
- conversion between frame index and timestamp.

### New `app/models/video_settings.py`

Keep video-specific controls separate from `AppSettings` so image projects and existing project files remain simple:

```python
@dataclass(slots=True)
class VideoSettings:
    start_frame: int = 0
    end_frame: int | None = None
    sample_every: int = 1
    max_frames: int = 256
    remove_near_duplicate_frames: bool = True
    duplicate_threshold: float = 0.995
    animation_fps: float | None = None
```

The duplicate filter should be conservative and operate on small grayscale thumbnails or perceptual hashes, not full-resolution frames. It should be opt-in or clearly reversible because subtle animation frames can be intentional.

### Extend `TileItem`

Add optional source metadata with defaults so old image projects still load:

```python
source_type: str = "image"
source_frame_index: int | None = None
source_timestamp_ms: int | None = None
source_path: str | None = None
```

For video tiles, `source_rect` remains useful for the applied crop and `source_size` remains the pre-normalization crop size.

### Extend `ProjectModel`

Add a `source_type` and optional `video_settings`/`video_metadata` state. Add methods analogous to the existing image methods:

- `add_video_frames(source, frame_refs, crop_rect=None)`;
- `add_video_frame(source, frame_ref, crop_rect=None)`;
- `reprocess_video_tiles(source)`;
- lookup of existing frame indices to prevent duplicates.

Project JSON should be versioned and retain backwards compatibility:

```json
{
  "schema_version": 2,
  "source_type": "video",
  "source_path": "clip.mp4",
  "video_settings": {"start_frame": 0, "sample_every": 2},
  "tiles": [
    {"name": "frame_0001", "source_frame_index": 12, "source_timestamp_ms": 400, "source_rect": [0, 0, 640, 360]}
  ]
}
```

When saving, prefer a path relative to the project file when possible. When loading, show a recoverable warning if the source was moved or its dimensions/frame count changed.

## UI changes

### File actions and source state

- Keep `Open Image...` for the current workflow.
- Add `Open Video...` with filters for common formats such as MP4, MOV, AVI, MKV, and WebM.
- Add drag-and-drop handling for both image and video files if practical.
- Replace the single-source assumption with a source state containing image/video kind, path, metadata, and current frame.
- Keep source loading and frame extraction errors in a status area plus a clear dialog for fatal errors.

### New `app/widgets/frame_browser.py`

Add a collapsible video-only panel between the Source Viewer and Final Preview, or as a bottom dock if the existing splitter becomes too crowded. Hide it for image sources.

The panel should contain:

- video metadata: dimensions, FPS, duration, and total frames;
- start/end frame or time controls;
- sampling controls: every N frames, target FPS, and maximum frame count;
- an Extract/Refresh button with progress and Cancel;
- a thumbnail list/grid with frame number and timestamp;
- single-click preview activation;
- Ctrl-click multi-select, Shift-click range selection, Select All, Clear, and Invert;
- a selected-count label;
- `Add Selected Frames to Bucket` and `Apply Current Crop to Selected` actions;
- an optional `Remove Near-Duplicate Frames` toggle with a visible result count.

Use a model/view list rather than eagerly creating a widget for every frame. Load thumbnails asynchronously and cap thumbnail resolution. Very long videos should remain responsive even when hundreds or thousands of candidate frames are available.

### Source Viewer integration

Keep the existing Select and Grid tools. Add:

- `set_frame(image, frame_ref)`;
- a `frameChanged` signal;
- keyboard shortcuts to move to previous/next extracted frame;
- a clear overlay indicating the current frame number/time;
- a shared crop action that applies the current selection rectangle to all selected frames.

For video mode, the viewer displays the activated frame while the frame browser owns the multi-selection. Do not make the user manually re-place the crop for every frame.

### Settings panels

Image/Grid mode keeps the existing Settings panel. Video mode switches the right-side control area to a dedicated Video Tool panel containing:

- frame output width and height, independent of image Tile/Selection size;
- Fit, Stretch, or Fill/Crop processing for frames as they enter the bucket;
- final tilesheet rows and columns;
- video-only background removal controls.

Video mode does not use the image Selection grid or Grid tool. Each left-clicked frame is added immediately and is processed with the current Video Tool settings. Keep an explicit Apply-to-existing-tiles action for intentional reprocessing after changing output settings.

The video-only background section should contain:

- Background removal mode: Off, Solid color, Edge-connected;
- current background color and tolerance;
- optional soft edge/feather amount to reduce color spill;
- `Detect from current frame`.

Keep the current solid RGB-distance algorithm as the baseline. Add the edge-connected mode in the image processor using a border flood fill/mask so internal pixels matching the background color are not removed accidentally.

The current recommended defaults remain appropriate for game sprites: fixed tile canvas, scale down only when needed, transparent trim enabled for video imports, and bottom-center anchor available for characters.

### Final preview

Keep the Sheet preview inline and add an `Open Animation Preview` action that opens a resizable modal:

- Play/Pause;
- FPS field or slider;
- loop toggle;
- current frame counter.

The modal animation preview should play the processed bucket tiles in their current order, so manual reordering is immediately visible.

## Processing pipeline

For each selected `FrameRef`:

1. Decode the frame through the source adapter/cache.
2. Apply the shared crop rectangle, or use the full frame when no crop is selected.
3. Convert to RGBA.
4. Remove background using the stable sequence color and selected mode.
5. Apply optional feathering and transparent-edge trimming.
6. Scale according to the existing scale mode and padding.
7. Place on the fixed transparent tile canvas using the selected anchor.
8. Create a `TileItem` containing the processed image and frame metadata.
9. Append in source order, skipping already-added frame indices.
10. Refresh bucket, sheet preview, animation preview, and source overlays.

Process selected frames in a worker with progress and cancellation. If one frame fails, report its index/time and leave the existing bucket unchanged; the batch operation should be atomic like `add_tiles_from_rects()`.

## Export changes

### PNG sheet

Reuse `export_sheet()` and `build_sheet()` so the output remains a standard transparent PNG with the existing tile width, height, rows, and columns.

Add a clear capacity warning before export and show the exact output dimensions.

### Optional metadata sidecar

Add an `Export Metadata...` or `Export Sheet + Metadata...` action that writes JSON beside the PNG. Include:

- source video path;
- source dimensions, FPS, and duration;
- output tile size and sheet grid;
- animation FPS;
- for every tile: bucket index, name, sheet rectangle, source frame index, source timestamp, and crop rectangle.

This makes the result easier to wire into Godot, Unity, or a custom engine and preserves the timing information that a PNG cannot contain.

### Individual frame export

Extend the existing individual tile export naming for video tiles, for example:

```text
001_frame_0012_t000400ms.png
```

Keep the existing image naming behavior unchanged.

## Testing plan

### Core tests

Add unit tests for:

- video metadata validation and frame/timestamp conversion;
- deterministic range, every-Nth, target-FPS, and max-frame selection;
- duplicate-frame filtering with similar and intentionally different synthetic frames;
- sequential extraction cancellation and error reporting using a fake source;
- video tile processing with full-frame and shared-crop modes;
- stable background color producing consistent alpha across frames;
- edge-connected background removal preserving interior matching-color pixels;
- atomic batch add when a frame fails;
- frame metadata serialization and schema migration;
- sheet order and exported metadata rectangles.

### Qt smoke tests

Add offscreen tests that:

- open a small generated test video;
- show video metadata and populate the frame browser;
- activate a frame and update the Source Viewer;
- select a range and add it to the bucket in source order;
- apply one crop to multiple selected frames;
- cancel an extraction without leaving partial state;
- play the animation preview and verify the frame counter advances;
- export a PNG and metadata sidecar.

Keep all existing image, Grid, project, and settings tests passing.

## Implementation phases

### Phase 1 — Source abstraction and decoder

- Add `video_source.py` and `VideoMetadata`/`FrameRef`.
- Add OpenCV as a runtime dependency, with a clear import error if unavailable.
- Implement metadata read, frame decode, thumbnail generation, cache, worker progress, and cancellation.
- Add core tests with a generated synthetic video or a fake `FrameSource`.

### Phase 2 — Frame browser and viewer integration

- Add `FrameBrowser` and video-only layout integration.
- Add range/sampling controls and asynchronous thumbnail population.
- Add current-frame state/signals to `MainWindow` and `SourceViewer`.
- Add Open Video and drag/drop support.

### Phase 3 — Sequence processing and model persistence

- Extend `TileItem` and `ProjectModel` with frame metadata.
- Add selected-frame batch processing, shared crop, source-order insertion, duplicate prevention, and atomic failure handling.
- Add stable background sampling and edge-connected removal.
- Add versioned project save/load with relative paths and missing-source recovery.

### Phase 4 — Animation and export

- Add Sheet/Animation preview controls.
- Add video-aware tile names and optional JSON metadata export.
- Verify output with a real game-engine import smoke check if available.

### Phase 5 — Polish and packaging

- Add checkerboard transparency preview if not already present.
- Add keyboard shortcuts for frame navigation and selection.
- Add recent sources and a compact empty state for the frame browser.
- Update README, Known Limitations, and PyInstaller packaging for the decoder dependency.
- Test large-video responsiveness, cancellation, source replacement, and memory usage.

## Acceptance criteria

- A user can open a supported video and see its dimensions, FPS, duration, and frame count.
- The app can extract a bounded, configurable list of candidate frames without freezing the UI.
- The user can preview individual frames, select individual frames or ranges, clear/invert/select all, and see the selected count.
- Selected frames can be added to the existing bucket in source order, with duplicate frame indices prevented.
- One crop rectangle can be applied consistently to all selected frames.
- Background removal works for the full selected sequence with a stable color/tolerance, and the output is transparent where expected.
- Every resulting tile has the configured final dimensions and is usable by the existing sheet builder.
- The final PNG is a valid transparent game sprite sheet and the animation preview reflects bucket order and FPS.
- Optional metadata identifies each output tile's source frame and timestamp.
- Existing image, Grid, background detection, project, and export workflows remain functional.
- Automated tests and compile checks pass.

## Non-goals for the first release

- Full AI segmentation or rotoscoping.
- Per-frame hand editing or per-frame crop rectangles.
- Audio import or synchronization.
- Automatic sprite action recognition.
- Direct generation of engine-specific project files; metadata JSON is the safer first integration point.

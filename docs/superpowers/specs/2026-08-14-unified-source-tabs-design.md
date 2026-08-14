# Unified Source Tabs Design

Date: 2026-08-14

## Summary

Sprite Sheet Cleaner will support multiple image and video sources in one project through a single source-tab system. Every source keeps independent working state, while all sources contribute to one ordered bucket, one final tilesheet, and one export pipeline.

Opening another source will append a tab instead of replacing the active source or clearing the bucket. Bucket tiles remain self-contained snapshots and continue to work after their source tab is closed or their source file becomes unavailable.

## Goals

- Allow several still images to remain open in separate tabs.
- Unify image and video tabs instead of maintaining separate media workflows.
- Build one bucket from any combination of image crops and video frames.
- Preserve per-source viewer, selection, grid, background-processing, paint, and video-extraction state.
- Preserve project-wide output dimensions, bucket order, undo/redo, preview, and export.
- Restore source tabs from saved projects using relative paths when possible.
- Keep bucket snapshots usable when a source is closed, moved, or missing.
- Migrate existing single-image, single-video, and multi-video projects.

## Non-goals

- Embedding complete source images or videos in `.sscproj` by default.
- Running multiple optional AI inference jobs concurrently.
- Adding multiple buckets.
- Adding cloud-backed sources, remote URLs, or collaborative editing.
- Persisting an unreviewed source-processing candidate across application restarts.
- Redesigning the established visual theme or the image-processing algorithms.

## Product model

The application has two ownership levels.

### Project-wide state

Project-wide state includes:

- the ordered bucket and its command stack;
- bucket/output tile width and height;
- final sheet rows and columns;
- final preview and export state;
- the source registry and visible tab order;
- the active source ID;
- an optional source ID whose Grid geometry controls final-sheet dimensions.

Changing project-wide bucket dimensions continues to resize every existing bucket tile atomically through one undoable command.

### Per-source state

Every source document owns state that must not leak into another tab:

- stable source ID, media type, canonical path, display name, and fingerprint;
- availability and relink status;
- source-specific processing and insertion settings;
- current selection and Selection-grid geometry;
- Grid origin and pending Grid selection;
- zoom, pan, and last pointer position;
- paint target and source-review state;
- source-processing repository and active/candidate revisions for images;
- frame-browser, sampling, current-frame, selection, and cache state for videos;
- job generation used to reject stale asynchronous results.

## Architecture

### `SourceWorkspace`

Add a UI-independent `SourceWorkspace` as the authoritative source registry and tab-order model. It exposes operations analogous to:

```python
add_document(document) -> source_id
activate(source_id) -> SourceDocument
close_tab(source_id) -> CloseResult
reopen(source_id) -> SourceDocument
relink(source_id, path) -> RelinkResult
document(source_id) -> SourceDocument | MissingSourceDocument
find_by_canonical_path(path) -> SourceDocument | None
open_source_ids() -> list[str]
```

The workspace rejects duplicate open canonical paths by activating the existing source. Source identity is persisted and is not derived solely from a mutable path.

Closing a tab removes its ID from visible tab order but retains its source descriptor while any tile references it. Reopening the same canonical source reuses that source ID. Source descriptors with no open tab and no referencing tile may be removed.

### Source document boundary

Define a small common document contract rather than forcing image and video implementations into one large class. The shared contract provides identity, path, display metadata, availability, view state, serialization, activation, deactivation, and close-job handling.

Concrete units:

- `ImageDocument` owns a `SourceRepository`, the active image, image-source settings, and image viewer state.
- The existing `VideoDocument` is extended with common identity/view fields and serialization hooks while retaining its frame-browser and video-specific behavior.
- `MissingSourceDocument` owns serialized state and provenance but no decoded pixels. It supports relinking and safe bucket-only use.

These units do not own the bucket, output settings, command stack, or export pipeline.

### Main-window responsibilities

`MainWindow` remains the Qt composition root, but it no longer owns parallel fields such as the sole `source_image`, sole `source_repository`, `video_source_path`, and `video_documents` collection as independent authorities.

It will:

- bind the unified tab widget to `SourceWorkspace`;
- activate a document into the shared Source Viewer;
- show the controls appropriate for the active media type;
- show the active video's existing frame browser in a contextual region;
- route source commands and asynchronous results using source ID and generation;
- refresh shared bucket/output controls after project mutations.

Source-specific behavior should move behind document/workspace helpers rather than adding more media branches to `MainWindow`.

## Settings separation

The existing settings types combine source, insertion, bucket, and sheet concerns. Multi-source support requires explicit ownership.

### Shared output settings

Shared output settings contain:

- bucket/output tile width and height;
- bucket aspect lock;
- output resampling used by project-wide bucket resize;
- final sheet rows and columns;
- optional Grid-match source ID.

### Image-document settings

Each image document retains:

- source selection width and height and aspect lock;
- Selection-grid rows and columns;
- background remover, color, tolerance, thresholds, model, and compute preference;
- trim behavior;
- on-add resize mode, resampling, padding, anchor, and edge bleed.

### Video-document settings

Each video document retains:

- extraction range, sampling, target FPS, maximum frames, and duplicate filtering;
- background-processing settings;
- on-add resize mode, resampling, padding, anchor, and seed-frame count;
- per-frame resize overrides.

Video frame width/height and image bucket width/height no longer compete as separate final canvas authorities. All additions normalize into the current project-wide bucket size.

An implementation may retain `AppSettings` as a compatibility facade during migration, but persisted schema-4 ownership and runtime authority must follow this split.

### Match final sheet to Grid

The current `match_sheet_to_grid` behavior becomes an optional `sheet_match_source_id`.

- Enabling **Match final sheet to this Grid** binds the shared sheet dimensions to the active image source.
- Switching tabs does not silently change that binding.
- Enabling it on another image transfers the binding.
- Closing or losing the bound source preserves the last valid sheet dimensions and shows that matching is paused.
- Video sources cannot become Grid-match sources.

## Unified tab interface

Place a single closable source-tab strip directly above the shared Source Viewer. Replace the video-only tab widget as a navigation authority.

Each tab contains:

- an image or video icon;
- a shortened filename;
- a modified/candidate indicator when applicable;
- a missing-source warning indicator when applicable;
- a close affordance;
- a tooltip containing the full source path.

Interaction rules:

- **Open Image** and **Open Video** append and activate tabs.
- Opening an already-open path activates its tab.
- Opening a source never clears the bucket.
- Switching tabs restores that document's viewer, tool, controls, geometry, and view state.
- Image tabs show image/Grid and Source Background controls.
- Video tabs show Video Tool controls and the active document's frame browser.
- Closing the active tab activates the nearest remaining tab.
- Closing the final tab leaves an empty source viewer while bucket editing, preview, and export remain available.
- Source tabs may be reordered; saved projects preserve the order.

The visual treatment follows the existing application. The distinctive multi-source cue is provenance: tabs and bucket rows use the same media icon and source filename, without relying on color as the sole identifier.

## Bucket provenance and source-scoped behavior

Add a non-null `source_id` to every newly created `TileItem`. Retain `source_path` for diagnostics, export metadata, and schema migration, but use `source_id` for runtime identity.

Bucket rows show a compact source marker consisting of media icon and abbreviated source filename. The full path appears in a tooltip. Missing and closed sources remain identifiable.

All crop/frame addition paths stamp the active document's source ID. Duplicating a tile preserves it.

Source-dependent behavior is scoped as follows:

- Grid duplicate detection keys image tiles by `(source_id, source_rect)`, so identical rectangles from different images remain distinct.
- Video duplicate detection keys frames by `(source_id, frame_index)` instead of path alone.
- **To Bucket** updates only image tiles whose `source_id` matches the active image document.
- Reprocessing a video updates only frames belonging to that video document.
- Candidate activation changes only future extraction from its image document.
- Source overlay markers show only bucket selections belonging to the active source.
- Animation preview retains its current active-video filtering; the final-sheet preview always shows the entire bucket.

Selecting a bucket tile whose source is not open previews its stored snapshot. Source-dependent actions are disabled with an explanation and a **Reopen/Relink Source** action.

## Tab closing and source lifetime

Closing a tab never removes bucket tiles.

Before close:

- cancel and settle active jobs owned by that source;
- reject late results using the document generation;
- warn if an unreviewed candidate would be discarded;
- preserve serializable settings, provenance, and view state.

Large decoded images, video frame caches, and revision pixels may then be released. Reopening reloads the original file and restores serialized state. An active processed revision is restored from its recorded recipe/cache entry when available; otherwise the original opens with a clear **Processing must be rerun** state. Bucket snapshots remain unchanged.

## Asynchronous job safety

Every source job carries:

- source ID;
- document generation;
- unique job/request ID;
- source fingerprint where applicable.

Completion, failure, cancellation, and progress handlers apply updates only when all ownership values still match. Switching tabs does not cancel a job. Closing, relinking, or replacing a source invalidates its generation and cancels its jobs.

For the first implementation, allow at most one source-processing inference job and one bucket-tile inference job project-wide. This preserves current optional-runtime and GPU ownership rules. The owning tab displays progress even when inactive; activating it reveals full status and cancellation controls.

A result for an inactive but still-valid document is stored on that document and marks its tab. A stale result must not change the active viewer, controls, candidate, bucket, or progress button.

## Project schema and persistence

Advance `.sscproj` to schema version 4.

Representative manifest shape:

```json
{
  "schema_version": 4,
  "sources": [
    {
      "source_id": "e154...",
      "source_type": "image",
      "path": "sources/character.png",
      "display_name": "character.png",
      "fingerprint": "sha256...",
      "source_size": [1024, 1024],
      "open": true,
      "tab_order": 0,
      "settings": {},
      "view_state": {},
      "active_processing_recipe": null
    }
  ],
  "active_source_id": "e154...",
  "output_settings": {},
  "sheet_match_source_id": null,
  "tiles": [
    {
      "tile_id": "8e40...",
      "source_id": "e154...",
      "source_type": "image",
      "source_path": "sources/character.png",
      "source_rect": [0, 0, 256, 256]
    }
  ]
}
```

Persistence rules:

- Make paths relative to the project directory when possible.
- Do not embed complete sources by default.
- Continue embedding exact bucket/base tile snapshots in `.sscproj`.
- Persist all source descriptors referenced by an open tab or bucket tile.
- Persist open/closed state, visible tab order, active source, source settings, and serializable view state.
- Do not serialize an unreviewed candidate; warn before save and allow the user to return to it or save without it.
- Retain active processing recipe metadata and cache identity, but do not claim a revision is restored unless its pixels are available and fingerprint validation succeeds.
- Treat `.sscproj` as the primary mixed-source format. Legacy JSON remains importable but is not the recommended authoring format.

Archive validation must accept only the existing project manifest and tile snapshot entries unless a later explicitly specified feature adds embedded sources. Existing entry-count, byte, pixel, traversal, and atomic-save protections remain in force.

## Migration

Schema-2 and schema-3 migration produces schema-4 runtime data before models are populated.

### Existing image project

- Create one image source from `source_image_path`.
- Assign a generated stable source ID.
- Map every image tile to that source unless a valid tile path identifies another legacy source.
- Split legacy `AppSettings` into source settings and shared output settings without changing rendered tile size.

### Existing video project

- Create one video source from the legacy source path and video settings.
- Map every video tile to it.

### Existing video collection

- Create one source per `video_sources` entry, preserving order.
- Map tiles by normalized path, then frame metadata.
- Preserve existing per-video settings and selection state.

Migration fails atomically when ownership is ambiguous rather than assigning a tile silently to the wrong source. The loader reports the affected tile/source and leaves the current project untouched.

## Missing sources and relinking

Project loading does not fail merely because one or more sources are missing.

- Create a `MissingSourceDocument` placeholder for each unavailable source.
- Load all embedded bucket snapshots and shared output state.
- Keep export, reorder, rename, duplicate, delete, transform, and bucket Paint Cleanup available.
- Disable crop, Grid, source Paint Cleanup, candidate processing, and source reprocessing for the missing document.
- Offer **Relink**, **Locate All**, and **Close Tab** actions.

Relinking validates media type, dimensions, and fingerprint. An exact fingerprint relinks immediately. A mismatched fingerprint requires explicit confirmation and does not rewrite existing bucket snapshots. Source-dependent reprocessing remains disabled until the mismatch is accepted.

## Error handling and atomicity

- Opening a corrupt or unsupported source leaves existing tabs and bucket state unchanged.
- Adding a source that fails after partial initialization removes the partial document and tab.
- Batch tile/frame additions remain atomic.
- Project load builds and validates a temporary workspace/model before replacing the current session.
- Project save writes the complete registry and tile snapshots atomically using the existing temporary-file/backup flow.
- Closing a source with an active job waits for terminal cancellation before releasing its resources.
- A stale job cannot clear another document's job state or reset the wrong progress UI.
- Capacity errors apply to the shared bucket regardless of active source.
- Relinking never mutates existing bucket snapshots automatically.

## Testing strategy

### Unit tests

- SourceWorkspace add, activate, reorder, close, reopen, and canonical-path deduplication.
- Source descriptor retention while referenced by bucket tiles and cleanup when unreferenced.
- Image and video document serialization.
- Per-document settings isolation.
- Grid duplicate keys using source ID plus rectangle.
- Video duplicate keys using source ID plus frame index.
- Source-scoped candidate application and video reprocessing.
- Schema-2/3-to-4 migration for image, video, and video collection projects.
- Missing-source placeholder and exact/mismatched relink validation.
- Stale job result rejection by source ID, generation, request ID, and fingerprint.

### Qt integration tests

- Open two images and one video; verify one ordered unified tab strip.
- Add crops/frames from every tab and verify one ordered bucket and final sheet.
- Switch tabs and verify selection, Grid, zoom/pan, controls, candidate state, and video browser isolation.
- Open a second image without clearing bucket or undo history.
- Close a source tab and verify its bucket tiles remain editable/exportable.
- Preview a stored tile from a closed or missing source.
- Reopen a closed path and verify source identity is reused.
- Complete a background job on an inactive tab and verify only its state/indicator changes.
- Close or relink a source during a job and verify its late result is ignored.
- Verify **To Bucket** changes only tiles from the active image source.
- Save/load tab order, active tab, per-source state, mixed provenance, output settings, and bucket pixels.
- Load with missing sources, export successfully, then relink.
- Bind final-sheet dimensions to one image Grid and verify tab switches do not change the binding.

### Regression tests

- Existing single-image workflow, background candidate workflow, Grid tools, Paint Cleanup, transforms, and exports.
- Existing single-video and multi-video extraction, animation preview, metadata export, and reprocessing.
- Existing schema-2 and schema-3 `.sscproj` archives and legacy JSON imports.
- Existing archive safety limits and atomic save behavior.

## Implementation boundaries

The work is one feature but should land in independently verifiable slices:

1. Introduce source identity, workspace, and document serialization without changing visible behavior.
2. Split settings ownership behind compatibility adapters.
3. Replace video-only navigation with unified source tabs.
4. Make additions, overlays, duplicate detection, candidate application, and reprocessing source-aware.
5. Add schema-4 save/load, migration, missing-source placeholders, and relinking.
6. Add job ownership/generation routing and close/relink cancellation safety.
7. Finish provenance UI, help text, and end-to-end regression coverage.

Each slice must keep the existing single-image and multi-video workflows functional.

## Acceptance criteria

- A user can open multiple images and videos as tabs in one project.
- Opening additional sources never clears existing bucket content.
- Every source restores independent working state when activated.
- Tiles from all source types coexist in one ordered, fixed-size bucket and final sheet.
- Every tile has stable, visible source provenance.
- Closing a tab never removes its tiles.
- Closed or missing sources do not prevent snapshot-only bucket editing or export.
- Source-dependent changes affect only tiles belonging to the selected source.
- Saved `.sscproj` projects restore unified tabs and mixed-source buckets, or show relinkable placeholders.
- Existing projects migrate without changing their rendered bucket pixels.
- Stale asynchronous results cannot affect another source or the active UI.
- Existing image and video test suites remain green.

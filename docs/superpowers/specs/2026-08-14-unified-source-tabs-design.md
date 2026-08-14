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
- Restoring processed source pixels from an external cache after a project restart.
- Bulk **Locate All** source discovery; the first release relinks one source at a time.
- Rebuilding historical/unknown-fingerprint tiles from an accepted replacement source.
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

Source identity is a persisted UUID. A canonical path is a locator, not identity. The workspace enforces at most one retained descriptor per canonical path:

- A matching path and fingerprint activates or reopens the existing source ID.
- If the path matches but its fingerprint changed, opening stops at a **Source changed** decision. The user may replace the retained source under its existing ID or cancel; the application does not silently merge the files or create a second descriptor for the same path.
- A relink target already owned by another descriptor is rejected and the owning source is identified. Source merging is not part of this release.
- Relative-path and case normalization occur before collision checks, using platform-appropriate path comparison.

Opening and relinking reserve the normalized canonical path before asynchronous fingerprinting begins. A second request for a reserved path focuses or reports the pending operation instead of creating another descriptor. Failure or cancellation releases the reservation; success converts it into the descriptor's owned path.

Closing a tab removes its ID from visible tab order but retains its descriptor for the life of the project. Reopening the same canonical source reuses that source ID. Descriptors are cleared only by creating/loading another project; an explicit source-forgetting UI is outside this release.

Fingerprinting is versioned and deterministic:

- Images use the existing decoded-pixel algorithm: SHA-256 over the ASCII prefix `"{width}x{height}:RGBA"` followed by row-major decoded RGBA bytes. The descriptor records `fingerprint_kind: "rgba-sha256-v1"`.
- Videos use SHA-256 over the complete file byte stream, read in bounded chunks. The descriptor records `fingerprint_kind: "file-sha256-v1"`. Hashing runs off the UI thread and participates in open/relink cancellation.
- Fingerprints created by another algorithm are not compared as exact matches.

### Source document boundary

Define a small common state contract rather than forcing image and video implementations into one large class. The shared contract provides identity, path, display metadata, availability, view state, serialization, activation, deactivation, and close-job handling. It contains no QWidget or other UI object so `SourceWorkspace` stays UI-independent.

Concrete units:

- `ImageDocument` owns a `SourceRepository`, the active image, image-source settings, and image viewer state.
- `VideoDocumentState` owns video metadata, settings, resize overrides, frame references, selection, and current-frame identity. The existing `VideoDocument` is split or adapted so it no longer owns `FrameBrowser`.
- `MissingSourceDocument` owns serialized state and provenance but no decoded pixels. It supports relinking and safe bucket-only use.

`MainWindow` or a dedicated Qt `SourceViewRegistry` owns each `FrameBrowser`, keyed by source ID. Browser widgets bind to `VideoDocumentState` when created and are destroyed or detached independently of serializable state.

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
- resize mode, resampling, padding, anchor, and edge bleed used when resizing existing bucket snapshots and rendering bucket transforms;
- final sheet rows and columns;
- optional Grid-match source ID.

Resizing existing bucket tiles always operates on their stored editable base snapshots. It never reloads or reprocesses a source. The shared output policy determines how each snapshot is placed onto the new common canvas, and the whole change remains one undoable command.

### Image-document settings

Each image document retains:

- source selection width and height and aspect lock;
- Selection-grid rows and columns;
- full-source candidate settings: engine, color/tolerance or model thresholds, model ID, compute preference, and post-processing controls used by Source Background;
- independent on-add tile-removal settings: enabled state, tile engine, color, tolerance/thresholds, model ID, compute preference, and post-processing controls used when a crop enters the bucket;
- trim behavior;
- on-add resize mode, resampling, padding, anchor, and edge bleed.

Changing full-source candidate settings never changes tile-removal controls, and changing tile-removal controls never rewrites or reruns a source candidate. Schema-3 migration obtains full-source controls from the persisted source-processing recipe/panel state when present and tile-removal controls from legacy `AppSettings`; missing full-source controls use current Source Background defaults.

Image insertion creates a temporary bucket-normalization policy from the project-wide output dimensions plus this document's on-add policy. It does not mutate shared output policy.

### Video-document settings

Each video document retains:

- extraction range, sampling, target FPS, maximum frames, and duplicate filtering;
- background-processing settings;
- on-add resize mode, resampling, padding, anchor, and seed-frame count;
- per-frame resize overrides.

Legacy video `frame_width`, `frame_height`, and `lock_frame_aspect` no longer remain independent final-canvas authorities. All new additions normalize into the current project-wide bucket size and aspect lock. Current video resize mode and anchor migrate to the video's on-add policy; resampling derives from `pixel_art_mode` (`nearest` when true, otherwise `smooth`); video padding defaults to `0`; edge bleed migrates from the legacy project bucket setting.

For a new project, the first opened source uses the application's current defaults. Every later source copies source-specific defaults from the most recently active document of the same media type, while shared output settings remain unchanged. Opening a project uses only persisted/migrated values.

An implementation may retain `AppSettings` as a compatibility facade during migration, but persisted schema-4 ownership and runtime authority must follow this split. Schema-3 migration copies the legacy bucket resize mode, resampling, padding, anchor, and edge bleed into both the shared existing-snapshot policy and the single source's on-add policy, preserving old behavior without leaving ambiguous ownership.

### Match final sheet to Grid

The current `match_sheet_to_grid` behavior becomes an optional `sheet_match_source_id`.

- Enabling **Match final sheet to this Grid** binds the shared sheet dimensions to the active image source.
- Switching tabs does not silently change that binding.
- Enabling it on another image transfers the binding.
- Closing or losing the bound source preserves the last valid sheet dimensions and shows that matching is paused.
- Reopening or exactly relinking the same current fingerprint automatically resumes matching once that source has a valid Grid; its Grid dimensions become authoritative again.
- Accepting a changed fingerprint or different-size replacement keeps matching paused. The user must explicitly choose **Resume matching to this Grid**, which warns that current sheet dimensions will be replaced.
- While matching is paused, sheet dimensions are editable and remain unchanged until automatic exact-source resumption or explicit replacement-source resumption.
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

Add non-null `source_id`, `source_fingerprint_kind`, and `source_fingerprint` values to every newly created `TileItem`. Retain `source_path` as immutable creation-time provenance for diagnostics, export metadata, and schema migration, but use `source_id` for runtime identity. Relinking never rewrites a pre-existing tile's recorded path, fingerprint kind, or fingerprint; tiles added after an accepted replacement record the replacement's current values.

Bucket rows show a compact source marker consisting of media icon and abbreviated source filename. The full path appears in a tooltip. Missing and closed sources remain identifiable.

All crop/frame addition paths stamp the active document's source ID. Duplicating a tile preserves it.

Source-dependent behavior is scoped as follows:

- Grid duplicate detection keys image tiles by `(source_id, source_fingerprint, source_rect)`, so identical rectangles from different images or accepted source replacements remain distinct.
- Video duplicate detection keys frames by `(source_id, source_fingerprint, frame_index)` instead of path alone.
- **To Bucket** updates only image tiles whose `source_id` and `source_fingerprint` match the active image document and candidate.
- Reprocessing a video updates only frames whose source ID and fingerprint match that video document's current file.
- Candidate activation changes only future extraction from its image document.
- Source overlay markers show only bucket selections belonging to the active source and current fingerprint. Historical-version tiles remain visible in the bucket but do not mark current Grid cells as already added.
- Animation preview retains its current active-video filtering; the final-sheet preview always shows the entire bucket.

Selecting a bucket tile whose source is not open previews its stored snapshot. Source-dependent actions are disabled with an explanation and a **Reopen/Relink Source** action.

Tiles from an older or unknown fingerprint are never silently rebuilt from an accepted replacement, and source-dependent reprocessing skips them. They remain usable as self-contained snapshots. In the first release, users create replacement-version tiles by adding the desired crop/frame again; cross-version historical rebuilding is deferred.

## Tab closing and source lifetime

Closing a tab never removes bucket tiles.

Close follows a transactional sequence:

1. If an unreviewed candidate exists, ask **Cancel** or **Discard and Close** before mutating any state.
2. **Cancel** leaves the tab, candidate, jobs, active source, and tab order unchanged.
3. After **Discard and Close**, mark the tab as `closing`, disable its source actions, invalidate its job generation, and request cancellation of jobs owned by that source.
4. Complete the close only after every owned job emits one terminal signal. Candidate discard and pixel/cache release happen at this commit point.
5. If cancellation reports failure or does not settle within five seconds, abort the close, restore the tab to usable state, keep the candidate, and report that the job must finish or be cancelled before closing. The UI must not block while waiting.

Large decoded images, video frame caches, and revision pixels may then be released. Reopening loads `current_path` and restores serialized settings/view state. In this document, an image's “immutable original” means the unprocessed decoded pixels of its current accepted path/fingerprint; `original_path` and `original_fingerprint` are historical provenance and are not reopening targets after an accepted replacement. The last active processing recipe is restored as control values only; the source opens on its current immutable original with **Processing must be rerun** until the user runs it again. Bucket snapshots remain unchanged.

## Asynchronous job safety

Every source job carries:

- source ID;
- document generation;
- unique job/request ID;
- source fingerprint where applicable.

Completion, failure, cancellation, and progress handlers apply updates only when all ownership values still match. Switching tabs does not cancel a job. Closing, relinking, or replacing a source invalidates its generation and cancels its jobs.

For the first implementation, one project-wide processing-mutation slot permits either a source-processing job or a bucket-tile inference job, never both. This preserves optional-runtime/GPU ownership and gives the non-concurrency rule one meaning. Video decoding/thumbnail extraction uses separate per-video workers because it does not use an optional inference runtime or mutate the bucket.

A valid source-processing result for an inactive document is stored on that document and marks its tab. It does not change the active viewer.

A bucket-tile inference job is a different transaction:

- capture the owning source ID/generation, source fingerprint, target tile IDs or pending crop, bucket revision, and command-stack revision;
- disable all bucket-mutating actions until the job reaches one terminal state, while allowing tab switches, viewing, and cancellation;
- on success, verify every captured ownership/revision value and apply exactly one bucket command;
- on mismatch, discard the result without changing the bucket or undo stack.

A stale result of either kind must not change another document, the active viewer, controls, candidate, bucket, undo history, or progress button.

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
      "original_path": "sources/character.png",
      "current_path": "sources/character.png",
      "display_name": "character.png",
      "fingerprint_kind": "rgba-sha256-v1",
      "original_fingerprint": "sha256...",
      "current_fingerprint": "sha256...",
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
      "source_fingerprint_kind": "rgba-sha256-v1",
      "source_fingerprint": "sha256...",
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
- If any image has an unreviewed candidate, saving lists the affected tabs and asks **Cancel** or **Save without candidates**. Saving without candidates does not discard them from the running session; it only omits them from the archive.
- Retain the last active processing recipe as control/preset metadata, not as a restored active revision. Processed source pixels and external cache identity are not part of schema 4.
- Treat `.sscproj` as the primary mixed-source format. Legacy JSON remains importable but is not the recommended authoring format.

Schema invariants:

| Field | Invariant |
|---|---|
| `sources` | List of objects with unique, non-empty `source_id` values. |
| Source paths | `current_path` is nullable only for an unresolved source. Resolved canonical paths are unique across descriptors. `original_path` is retained for provenance and may be null only for migrated legacy data that never recorded it. |
| Source size | Positive width/height when known. It may be null only for unresolved migrated legacy descriptors whose old manifest did not record it. |
| Fingerprints | `fingerprint_kind`, `original_fingerprint`, and `current_fingerprint` may be null only for migrated legacy provenance that cannot be derived without a source. A known `original_fingerprint` never changes. A known `current_fingerprint` changes only after exact relink or explicit accepted replacement. |
| `open` / `tab_order` | Open sources have distinct dense integer orders `0..n-1`. Closed sources have `tab_order: null`. |
| `active_source_id` | Null exactly when no source is open; otherwise references an open source. |
| `sheet_match_source_id` | Null or references an image descriptor. It may reference a closed/missing image, in which case matching is paused. |
| Source settings | Discriminated and validated by `source_type`; image and video payloads cannot be interchanged. |
| `view_state` | Contains only serializable coordinates, tool IDs, selections, and Grid state. Loader clamps geometry to a successfully loaded source and clears invalid geometry. |
| Tiles | Every tile references an existing descriptor and carries immutable creation-time source type, path, fingerprint kind, and fingerprint. Fingerprint kind and fingerprint may be null only on a migrated legacy tile whose historical source fingerprint is unknowable. |

Persisted video state includes metadata needed for validation, sampling controls, extracted frame references, selected frame indices, current frame index, source-processing controls, seed count, and resize overrides. Thumbnail pixels, decoded-frame caches, workers, cancellation tokens, progress, and `FrameBrowser` widgets are ephemeral and are rebuilt after load.

Persisted image state includes selection dimensions/matrix, valid selection and Grid geometry, tool ID, zoom/pan, source-processing controls, and last active recipe preset. Original/active/candidate pixels, jobs, progress, and paint stroke working buffers are ephemeral.

Archive validation must accept only the existing project manifest and tile snapshot entries unless a later explicitly specified feature adds embedded sources. Existing entry-count, byte, pixel, traversal, and atomic-save protections remain in force.

Legacy JSON saving remains available only for a compatible single-source session. When more than one descriptor is open or referenced, the legacy save option is disabled with guidance to use `.sscproj`. Legacy JSON remains importable.

## Migration

Schema-2 and schema-3 migration produces schema-4 runtime data before models are populated. Migration first identifies the container because snapshot archives and source-dependent JSON have different guarantees.

| Input | Tile pixels | Source requirement | Pixel guarantee |
|---|---|---|---|
| Schema-2/3 `.sscproj` | Embedded base snapshots | Sources may be missing | Embedded tile pixels remain byte-equivalent after decode/encode-independent in-memory loading; migration does not rerender them. |
| Current video JSON/collection | No complete portable snapshot guarantee | Every referenced video required for source-dependent reconstruction | Existing validated frame/crop processing path is used. |
| Legacy image JSON | No snapshots | Referenced image required | Existing `legacy_v1_renderer` behavior is preserved; output depends on the located source matching the saved project. |

When a snapshot-backed archive is migrated while a source is missing, migration creates the descriptor with whatever historical path/type metadata exists and leaves unavailable dimensions, fingerprint kind, and fingerprints null. It does not invent provenance from tile pixels because a crop snapshot cannot fingerprint the complete source. Migrated tile fingerprints are likewise null unless the old manifest authoritatively supplied one. If the source is available, the loader computes the defined current fingerprint and dimensions; it still leaves `original_fingerprint` null when the historical identity cannot be proven.

### Existing image project

- Create one image source from `source_image_path`.
- Assign a generated stable source ID.
- Map every image tile to that source. Existing image schemas never authoritatively declared multiple image documents, so a stray tile path does not create an implicit source.
- Split legacy `AppSettings` into source settings and shared output settings without changing rendered tile size.

### Existing video project

- Create one video source from the legacy source path and video settings.
- Map every video tile to it.
- Derive shared bucket dimensions from validated embedded snapshot dimensions for `.sscproj`; otherwise use validated root output settings, falling back to the video target size only when root output geometry is absent.
- Map legacy frame aspect lock to shared bucket aspect lock only when root output settings do not provide it.

### Existing video collection

- Create one source per `video_sources` entry, preserving order.
- Build a unique normalized-path-to-source-ID map. Map each tile only by its normalized `source_path`.
- If a tile has no path and the collection has exactly one source, map it to that source. If more than one source exists, fail migration and name the ambiguous tile.
- Frame index/timestamp may validate a path-based mapping but never choose between sources.
- Preserve existing per-video settings and selection state.
- Derive shared output geometry from validated embedded snapshots or root output settings. If a JSON collection has conflicting video target sizes and no authoritative shared output geometry, fail with a message requiring the user to open/save it in the prior version or choose a target size during a dedicated import flow.

Migration fails atomically when ownership is ambiguous rather than assigning a tile silently to the wrong source. A missing collection tile path, duplicate normalized source paths, inconsistent embedded tile dimensions, invalid media type, or conflicting unresolvable output geometry is an atomic failure. The loader reports the affected tile/source and leaves the current project untouched.

## Missing sources and relinking

Project loading does not fail merely because one or more sources are missing.

- Create a `MissingSourceDocument` placeholder for each unavailable source.
- Load all embedded bucket snapshots and shared output state.
- Keep export, reorder, rename, duplicate, delete, transform, and bucket Paint Cleanup available.
- Disable crop, Grid, source Paint Cleanup, candidate processing, and source reprocessing for the missing document.
- Offer **Relink** and **Close Tab** actions.

Relinking validates canonical-path uniqueness, media type, dimensions/metadata, and fingerprint:

- A target path already owned by another descriptor is rejected; it never merges descriptors.
- An exact fingerprint relinks immediately, updates `current_path`, and preserves all source state.
- If legacy `current_fingerprint` is unknown, exact identity cannot be claimed. Relinking shows **Historical identity unverified** with known path/type/dimension evidence and requires explicit association. Acceptance sets `current_path`, `current_fingerprint`, `fingerprint_kind`, and current dimensions, while leaving unknown historical `original_fingerprint` null. Existing tile provenance remains unknown.
- A matching media type and dimensions with a different fingerprint requires **Accept Replacement** confirmation. Acceptance increments generation, sets `current_path` and `current_fingerprint`, and clears revisions, candidate state, decoded caches, and pending jobs. Image selection/Grid geometry remains because dimensions match. Existing bucket snapshots and their provenance remain unchanged.
- Different image dimensions require a stronger **Replace with Different Size** confirmation. Acceptance additionally clears the current selection and pending Grid selection, clamps Grid origin, rebuilds Grid geometry, and pauses Grid matching until a valid Grid is available.
- For a video whose dimensions, frame count, FPS, or duration changed, acceptance clears thumbnail/frame caches, current frame, and extracted/selected references; drops resize overrides for unavailable frame indices; and requires extraction again.
- A media-type mismatch is a hard failure and cannot be confirmed.

Source-dependent reprocessing remains disabled until any mismatch is explicitly accepted.

## Export compatibility

PNG sheet and individual-tile exports are unchanged because they consume stored bucket images.

Metadata export advances from schema version 1 to schema version 2. Schema 2 adds a `sources` table and records `source_id`, creation-time `source_path`, `source_fingerprint_kind`, and `source_fingerprint` for every tile/frame. Closed and missing descriptors remain in the table with availability state. Existing frame index, timestamp, crop, resize, and output rectangle fields remain unchanged.

Compatibility fields are deterministic and never depend on the active tab:

- With exactly one referenced source, top-level `source_path` identifies it. With more than one, `source_path` is null and `source_count` reports the number of referenced descriptors.
- With exactly one referenced video and no other source, top-level `video_metadata` and `animation_fps` preserve their schema-1 meanings for that video.
- With multiple videos or any image-plus-video mix, top-level `video_metadata` and `animation_fps` are null. Each video entry in `sources` contains its own media metadata and `animation_fps` (the video's source FPS under current behavior), and the existing `video_sources` projection carries the same per-video values for compatibility.
- Image-only exports set video compatibility fields to null.

Metadata export includes descriptors referenced by exported tiles, not unrelated empty tabs. Unknown migrated fingerprints are emitted as null rather than fabricated.

## Error handling and atomicity

- Opening a corrupt or unsupported source leaves existing tabs and bucket state unchanged.
- Opening a changed file at an already-retained path requires an explicit replace decision and never creates an implicit second identity.
- Adding a source that fails after partial initialization removes the partial document and tab.
- Batch tile/frame additions remain atomic.
- Project load builds and validates a temporary workspace/model before replacing the current session.
- Project save writes the complete registry and tile snapshots atomically using the existing temporary-file/backup flow.
- Closing a source with an active job uses the non-blocking transactional close flow; timeout aborts close without discarding the candidate or releasing source state.
- A stale job cannot clear another document's job state or reset the wrong progress UI.
- The global processing-mutation slot rejects a second source/tile inference request with a link to the owning tab and its Cancel control.
- Bucket mutations stay disabled during bucket-tile inference, and successful completion creates one command only after revision validation.
- Capacity errors apply to the shared bucket regardless of active source.
- Relinking never mutates existing bucket snapshots automatically.

## Testing strategy

### Unit tests

- SourceWorkspace add, activate, reorder, close, reopen, and canonical-path deduplication.
- Source descriptor retention after close until another project is created or loaded.
- Same-path unchanged reopen, same-path content replacement decision, in-flight canonical-path reservation, and relink collision rejection.
- Versioned decoded-RGBA image fingerprint and streaming file-byte video fingerprint fixtures.
- Image and video document serialization.
- UI-independent `VideoDocumentState` serialization without Qt widgets.
- Per-document settings isolation.
- Independence of full-source candidate controls and on-add tile-removal controls.
- Lossless mapping of every legacy image/video/output setting into schema-4 ownership, including video target size/aspect and derived resampling/padding defaults.
- Existing-snapshot resize using only shared output policy; source insertion using shared dimensions plus document policy.
- Grid duplicate keys using source ID plus fingerprint plus rectangle.
- Video duplicate keys using source ID plus fingerprint plus frame index.
- Source-scoped candidate application and video reprocessing.
- Schema-2/3-to-4 migration for image, video, and video collection projects.
- Separate snapshot-archive and legacy-JSON migration guarantees and atomic ambiguity failures.
- Missing legacy-source migration with nullable dimensions/fingerprints and explicit unverified relink association.
- Missing-source placeholder and exact/mismatched relink validation.
- Relink provenance immutability plus image/video state resets for accepted replacements.
- Stale job result rejection by source ID, generation, request ID, and fingerprint.
- Global processing-slot exclusion and bucket/command revision validation.

### Qt integration tests

- Open two images and one video; verify one ordered unified tab strip.
- Add crops/frames from every tab and verify one ordered bucket and final sheet.
- Switch tabs and verify selection, Grid, zoom/pan, controls, candidate state, and video browser isolation.
- Open a second image without clearing bucket or undo history.
- Close a source tab and verify its bucket tiles remain editable/exportable.
- Cancel a close at the candidate warning and verify no state changed.
- Time out job cancellation and verify close aborts without candidate loss.
- Preview a stored tile from a closed or missing source.
- Reopen a closed path and verify source identity is reused.
- After accepted replacement, reopen and verify `current_path` supplies the new immutable baseline while historical path/fingerprint remain provenance only.
- Change a file at the same path and verify replace/cancel behavior.
- Complete a background job on an inactive tab and verify only its state/indicator changes.
- Close or relink a source during a job and verify its late result is ignored.
- Attempt bucket mutation while bucket inference runs and verify it is disabled; verify completion creates one undo entry.
- Verify **To Bucket** changes only tiles from the active image source.
- Add identical image rectangles and video frame indices before and after accepted replacement; verify both versions coexist and old-version tiles are not silently reprocessed.
- Save/load tab order, active tab, per-source state, mixed provenance, output settings, and bucket pixels.
- Load with missing sources, export successfully, then relink.
- Relink to an already-owned path and verify the collision is rejected.
- Accept same-size and different-size image replacements and verify the defined state resets.
- Accept changed-video metadata and verify frame/browser state resets.
- Bind final-sheet dimensions to one image Grid and verify tab switches do not change the binding.
- Close an unreferenced Grid-match source and verify its descriptor/binding remain paused and recoverable.
- Edit sheet dimensions while Grid matching is paused; verify exact-source reopen resumes automatically and changed-source replacement requires explicit resume.
- Export schema-2 metadata fixtures for image-plus-video and multiple-video sessions with different FPS values; verify source table, null top-level mixed fields, compatibility projections, and immutable per-tile provenance.

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
- Existing snapshot-backed `.sscproj` projects migrate without rerendering their bucket pixels; legacy JSON continues through its established source-dependent renderer.
- Stale asynchronous results cannot affect another source or the active UI.
- Existing image and video test suites remain green.

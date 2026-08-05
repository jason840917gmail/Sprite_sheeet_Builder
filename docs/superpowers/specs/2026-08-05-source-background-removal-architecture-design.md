# Source-Level Background Removal and Optional AI Architecture

## Status

Approved in conversation on 2026-08-05.

## Goal

Replace the current per-tile, hard RGB background removal with a non-destructive source-level workflow that produces reliable straight-alpha RGBA assets for games. The application must keep its repository and core Python environment lightweight while allowing users to explicitly download, install, use, repair, and remove optional rembg and BEN2-based AI capabilities.

The design must also correct the application defects found during the repository audit, preserve existing project compatibility, keep the UI responsive, and make CPU fallback automatic when NVIDIA CUDA is absent or unusable.

## Product Decisions

- The current delivery target remains Python users running the project from source.
- Background removal is applied to the original source once, before tile extraction.
- The original source is immutable. Every successful application creates a new processed source revision.
- Extracted bucket tiles are stable snapshots. Creating or activating a new source revision never changes existing bucket tiles automatically.
- Users can explicitly apply the active source revision to selected or all bucket tiles after comparing the result.
- Optional AI frameworks run in isolated, application-managed virtual environments outside the repository.
- Models and framework packages require an explicit Install action in a Model Manager. There are no silent first-use downloads.
- Model licenses are shown but are not used to hide or block models.
- Compute defaults to Auto: validated NVIDIA CUDA first, then CPU fallback.
- AI models, framework wheels, processed-source caches, and logs are never committed to the repository.

## Current-System Findings

### Correctness

- `place_on_tile_canvas` and `build_sheet` pass an RGBA image as both the source and Pillow paste mask. This applies the source alpha repeatedly. A source alpha of 128 becomes approximately 64 on the tile canvas and 16 after sheet placement.
- Background removal is a binary Euclidean distance in sRGB. It cannot create antialiased edges, distinguish perceptual color differences, or protect disconnected foreground details that resemble the background.
- The dominant quantized border-bin detector can be misled by sprites touching the border, gradients, multiple border colors, and compression noise.
- Automatic detection enables removal and raises tolerance to at least 64 without requiring an explicit source-processing action.
- Straight-RGBA LANCZOS scaling can mix hidden background RGB into semitransparent edges and create fringes.
- No foreground RGB dilation exists beneath fully transparent pixels, leaving exports vulnerable to texture-filtering halos in game engines.

### Performance and responsiveness

- Every tile extraction repeats background removal even when every crop comes from the same source and uses the same settings.
- Any settings signal can synchronously reprocess all bucket tiles on the UI thread.
- Linked tolerance widgets can produce duplicate settings notifications.
- Bucket thumbnails and a complete final sheet are rebuilt synchronously during broad refreshes.
- There is no processing-job abstraction, cancellation, progress, worker recovery, cache key, or model-session reuse.
- Full-image NumPy copies, processed RGBA images, mattes, and preview sheets can create high peak memory use on large sources.

### Persistence and reliability

- Project JSON stores an absolute source path, which makes projects hard to move.
- Project loading reconstructs bucket pixels from the current source and settings rather than restoring the exact visual snapshots the user saved.
- The project format has no explicit schema version or general migration mechanism.
- Saving is not atomic and there is no dirty-document prompt, backup/recovery path, or normal Save versus Save As behavior.
- Destructive bucket actions and source-revision application have no undo.
- Errors are mostly modal strings without structured diagnostic history.

### Packaging and testing

- Core requirements are unpinned and there is no dependency lock strategy.
- AI packages would conflict if added directly to the current environment.
- The current core test suite passes in the available runtime, but 15 PySide6 UI tests are skipped there because PySide6 is unavailable.
- Coverage does not include soft alpha, color decontamination, texture-filtering halos, repeated alpha placement, large-image cancellation, project recovery, download failures, worker crashes, or GPU fallback.

## User Workflow

1. Open a source image. The application retains an immutable RGBA original.
2. Open the Source Background section and choose Exact Key, Smart Solid, rembg, or BEN2.
3. If an AI engine is not installed, open Model Manager and explicitly install it.
4. Adjust engine and cleanup settings while viewing a debounced preview region.
5. Inspect Original, Alpha Mask, Transparent Result, or a before/after comparison.
6. Press Apply to Source.
7. Follow nonmodal progress or cancel the operation. The previous active revision remains usable during failure or cancellation.
8. Review and activate the newly completed source revision.
9. Extract tiles cheaply from the active processed source.
10. If older bucket tiles exist, leave them unchanged and mark their source-revision difference. Offer Compare, Apply to Selected Tiles, and Apply to All Tiles.
11. Export individual tiles or a final straight-alpha RGBA PNG sheet.

## Architectural Boundaries

```text
PySide6 UI
    -> Controllers, commands, and job presentation
        -> Application services
            -> Domain models and engine interfaces
                -> Storage, cache, built-in engines, and AI worker client
                    -> Isolated AI worker environments and downloaded models
```

### UI layer

The UI renders state and translates user actions into commands. Widgets must not perform image inference, model installation, project serialization, or full-sheet export directly.

### Application services

- `SourceProcessingService` validates settings, builds cache keys, starts preview or apply jobs, and commits completed revisions atomically.
- `TileService` extracts a snapshot from a chosen revision and explicitly refreshes selected snapshots when requested.
- `ProjectService` loads, migrates, validates, saves, recovers, and tracks dirty state.
- `ExportService` performs preflight checks and atomic or staged output generation.
- `ModelManagerService` owns manifests, installation state, runtime creation, verification, repair, update, and removal.
- `JobController` owns progress, cancellation, mutually exclusive operations, worker lifecycle, and structured errors.

### Domain layer

The domain layer must not import PySide6, rembg, ONNX Runtime, PyTorch, or OS-specific UI code.

Split the current monolithic settings object into:

- `SourceProcessingSettings`: engine, model, thresholds, matte cleanup, despill, pixel-art mode, chunking, and compute preference.
- `TileSettings`: selection geometry, final tile dimensions, trim, scale, padding, and anchor.
- `SheetSettings`: rows, columns, grid matching, and export options.
- `UserPreferences`: model/cache locations, preview quality, default compute preference, and diagnostics choices.

### Infrastructure layer

- Built-in background engines and common matte post-processing
- AI worker protocol client
- Runtime and model registry
- Download transport and checksum validation
- Project bundle serializer and migrations
- Revision, matte, thumbnail, and export caches
- Structured logging and diagnostic export

## Domain Model

### `ProjectDocument`

Contains an explicit schema version, source reference, processing recipes, revision metadata, tile snapshots, tile/sheet settings, and UI-safe project state. It does not contain installed model weights or Python environments.

### `SourceAsset`

Contains a project-relative path when possible, an absolute fallback, file size, modification metadata, dimensions, and a content fingerprint. If a source cannot be found or its fingerprint changes, the user is offered Locate Source and a clear mismatch warning.

### `SourceRevision`

Contains:

- Stable revision identifier and optional parent identifier
- Source fingerprint
- Engine identifier and engine-settings snapshot
- Framework, model identifier, version, and model checksum
- Matte/post-processing recipe version
- Actual CPU or GPU backend used
- Creation timestamp and completion status
- Cache keys for the matte and processed RGBA source
- Small preview metadata suitable for project persistence

Only a fully completed, verified revision may become an activation candidate. Successful processing does not switch the active source automatically: the user compares the candidate and explicitly chooses Activate Revision. Failure, cancellation, or rejection leaves the prior revision active. Temporary results are never exposed as committed revisions.

### `TileSnapshot`

Contains:

- Stable tile identifier and display name
- Source crop rectangle
- Source revision identifier
- Tile-settings snapshot
- Exact persisted RGBA PNG asset within the project bundle
- Pixel dimensions and optional content hash

Changing the active source revision does not mutate this asset. Explicit refresh creates a replacement through an undoable command.

## Background Engine Contract

Every engine implements a small framework-independent contract:

- Describe engine identity, capabilities, availability, and settings schema.
- Validate settings and source constraints before a job starts.
- Produce a preview matte for a bounded region.
- Produce a full-source matte through a cancellable job.
- Return structured timing, backend, warnings, and model metadata.

The primary result is a single-channel matte, not an already-composited final PNG. A shared post-processing pipeline combines that matte with the original source consistently across built-in and AI engines.

Initial engines:

- `exact-key`: deterministic binary removal for crisp pixel art.
- `smart-solid`: recommended default for generated images with a solid or near-solid background.
- `rembg`: adapter for explicitly installed rembg-supported ONNX models.
- `ben2-onnx`: BEN2 Base through the managed ONNX runtime.
- `ben2-native`: optional later adapter if measured quality or performance justifies the much larger PyTorch environment.

## Common Image Pipeline

### 1. Preserve original alpha

Load the source as straight-alpha RGBA and retain its original alpha channel. A generated matte can reduce existing opacity but never invent opacity where the source is already transparent.

### 2. Robust solid-background estimation

Smart Solid samples visible border regions, excludes low-alpha samples, clusters likely background colors, and returns both the selected color and confidence. Low confidence is presented to the user rather than silently increasing tolerance.

### 3. Perceptual color representation

Convert source and candidate background colors from sRGB to a perceptual Lab representation for Smart Solid comparisons.

### 4. Perceptual distance

Use a documented perceptual color-distance calculation instead of Euclidean sRGB distance. Avoid square roots or conversions in repeated inner loops when equivalent precomputation is possible.

### 5. Two thresholds and a soft transition

Use separate transparent and foreground thresholds. Pixels between them receive a soft matte value. Exact Key bypasses this and remains binary.

### 6. Border-connected uncertainty resolution

Flood or region-grow only background-connected candidate pixels through the uncertain band. This protects similarly colored details enclosed within a foreground sprite.

### 7. Optional morphology

Allow a conservative one-pixel cleanup for isolated matte noise and pinholes. Disable it by default in pixel-art mode.

### 8. Edge despill and foreground-color reconstruction

For partially transparent boundary pixels, reduce the estimated background contribution in a suitable linear-light representation. Keep this strength adjustable and previewable.

### 9. Combine matte with original alpha

Compute final alpha from the generated matte and original alpha. Preserve the source RGB except where edge decontamination intentionally reconstructs it.

### 10. Correct tile and sheet placement

Copy non-overlapping RGBA tile pixels directly into transparent canvases rather than passing the source alpha as a second paste mask. Use an explicit alpha-composite operation only when true visual compositing is intended.

### 11. Transparent-pixel RGB dilation

Extend foreground RGB into fully transparent neighboring pixels without changing alpha. This supplies useful texture-filtering colors and prevents dark or background-colored fringes in game engines.

Dilation is an output-asset operation. Run it after the final tile resize, padding, and placement because premultiplication intentionally erases RGB where alpha is zero. A source revision may contain dilation for faithful previewing, but every persisted tile snapshot must repeat dilation after its last geometric transform. Assemble sheets from those prepared tile pixels without dilating across tile boundaries, so one atlas cell cannot borrow colors from a neighboring sprite.

### 12. Straight-alpha RGBA PNG export

Save standard RGBA PNG files with straight alpha. Validate mode, dimensions, alpha range, and output readability before reporting success.

### Premultiplied-alpha scaling

Any scaling step premultiplies RGB by alpha, resamples color and alpha consistently, then safely unpremultiplies back to straight alpha before storage or export. This prevents invisible RGB from contaminating antialiased edges.

Because zero-alpha RGB cannot survive premultiplication, transparent-pixel RGB dilation always follows the last premultiplied resize rather than preceding it.

## Source-Level Processing and Large Images

Background engines run once per source revision. Tile extraction reads a rectangular region from the active processed source and never invokes a background engine.

Built-in vectorized engines may process the full source directly within a memory budget. AI engines process large sheets as overlapping chunks, blend or select consistent overlapping matte regions, and write results into a bounded or disk-backed matte buffer. Chunk dimensions are derived from model input limits, available memory, overlap needs, and a user-overridable advanced setting.

Chunking is an implementation detail of the single Apply to Source action. The UI reports stages and aggregate progress rather than exposing tiles as independent inference jobs.

Cancellation, worker exit, out-of-memory, corrupt output, or disk-full errors discard temporary results and preserve the prior active revision.

## Rendering, Preview, and Export

- Source previews use a checkerboard that distinguishes transparent areas without modifying image pixels.
- Preview modes are Original, Alpha Mask, Transparent Result, and Before/After.
- Preview requests are debounced and cancellable; obsolete results are ignored through request identifiers.
- Full sheet previews use cached thumbnails or a scaled composite rather than rebuilding a full-resolution export after every UI change.
- Bucket thumbnails are cached by tile content hash and display settings.
- Export uses exact full-resolution tile snapshots, never preview images.
- Batch export writes staged outputs, validates them, and reports partial-cleanup status if finalization fails.

## Stable Bucket Updates and Undo

After a new source revision succeeds, existing tiles display a revision-difference indicator but remain byte-for-byte unchanged.

The user may compare the existing tile with a candidate regenerated from the active source revision, then choose Apply to Selected Tiles or Apply to All Tiles. The update is atomic for the requested set and records the previous snapshots in session command history. Delete, clear, duplicate, rename, reorder, and revision-application operations use the same undo/redo command mechanism.

Project save persists current snapshots. Session history may be cleared on close after dirty-state handling; persistent cross-session undo is out of scope.

## Model Manager and Optional Runtime Isolation

### Storage

Use a platform-appropriate user-data root, such as `%LOCALAPPDATA%/SpriteSheetCleaner` on Windows:

```text
SpriteSheetCleaner/
    runtimes/
        onnx/
        ben2-native/
    models/
        rembg/
        ben2/
    cache/
    downloads/
    logs/
```

The repository holds only lightweight provider code, versioned manifests, schema definitions, and checksums.

### Manifests

Each engine/model manifest records:

- Stable identifier and display name
- Framework and locked package versions
- Model version, source URL, checksum, and expected sizes
- License and upstream project links
- CPU/GPU support and known runtime constraints
- Input resolution, recommended chunking, and measured RAM/VRAM guidance
- Adapter protocol version and compatible application versions

License information is visible but does not filter or block installation.

### Installation state machine

Model Manager exposes Not Installed, Downloading, Verifying, Installing, Testing, Ready, Update Available, Incompatible, and Repair Needed states.

Downloads go to temporary or resumable files, are checksum-verified, and move into final storage atomically. Installation creates or updates a provider-specific virtual environment without modifying the repository or the core environment. Repair recreates damaged environments from the locked manifest. Uninstall removes only the resolved provider/model targets and reports recoverability.

Python package locks include artifact hashes and platform/Python compatibility markers, and installation uses hash-required mode. Because managed virtual environments inherit the interpreter that launched the source application, every runtime manifest declares supported host-Python versions. Model Manager reports Incompatible before downloading when the host interpreter has no verified lock. Downloading a separate Python distribution is out of scope for this iteration.

Every managed runtime and model occupies an application-created leaf directory with an ownership marker containing its identifier and manifest version. Before repair or uninstall, canonicalize the configured root and target; require the target to be a marked descendant strictly below that root; reject the root itself, shared parents, symbolic links, junctions, reparse points, and paths that escape containment. Uninstall enumerates and removes only manifest-owned files and refuses unknown user-created content rather than recursively deleting it.

Installed engines work offline. Missing network access never prevents the core application, built-in engines, existing projects, or exports from working.

### Initial runtime strategy

- Use one managed ONNX environment for rembg and BEN2 ONNX where compatible.
- Select a locked ONNX Runtime CPU or CUDA profile through the manifest and capability service.
- Prefer BEN2 ONNX before native PyTorch to reduce installation size and dependency complexity.
- Add native BEN2 only after representative asset benchmarks demonstrate a useful advantage.

The rembg adapter must not use rembg's implicit first-inference model download. Model Manager preinstalls and verifies every requested weight, launches the worker with rembg's model directory set to the exact managed location, and performs a checksum preflight before session creation. A missing or damaged weight produces a Repair Required or Not Installed result; it never triggers network access from inference. The same explicit-install rule applies to auxiliary model files.

## GPU Discovery and Fallback

Hardware presence alone is insufficient. Auto selection performs:

1. NVIDIA hardware and free-VRAM discovery when available.
2. Runtime library loading.
3. Execution-provider discovery.
4. A small real session or model warm-up test.
5. A memory preflight using model guidance and current free memory.

If validation succeeds, use CUDA. If CUDA initialization, allocation, or inference fails, retry with a smaller supported chunk where appropriate, then fall back to CPU. The result metadata and job UI report the actual provider and reason for fallback.

Users may choose Auto, NVIDIA GPU, or CPU. Auto is the default. An explicit NVIDIA GPU choice produces a clear error rather than silently falling back unless the user has enabled fallback for forced modes.

For PyTorch-backed providers, the worker uses PyTorch's runtime availability check and an allocation/warm-up test. For ONNX-backed providers, it validates the CUDA execution provider and a real session rather than trusting device enumeration.

## Worker Protocol and Job Lifecycle

The main application never imports optional AI frameworks. It launches a provider worker from the corresponding managed environment.

- Use a versioned, structured JSON message protocol over standard streams or another explicitly framed local transport.
- Exchange large source, matte, and result data through validated temporary file paths or bounded shared storage, not JSON blobs.
- Do not exchange Python pickle data.
- Include request identifiers, protocol version, operation, input descriptors, settings, progress, cancellation acknowledgment, result metadata, and structured errors.
- Keep a compatible worker alive to cache the selected model between jobs.
- Shut down or restart a worker after incompatibility, timeout, unrecoverable error, environment repair, or user-requested memory release.
- Cancellation first requests a cooperative stop, then terminates an unresponsive isolated worker after a grace period.

The UI remains responsive throughout model installation, model loading, preview inference, full-source processing, cache validation, and export.

## Project Format and Cache

### `.sscproj` bundle

Introduce `.sscproj` as a single ZIP-based project file containing:

- `project.json` at the archive root
- Exact bucket snapshot PNG files under `tiles/<tile-id>.png`
- Small project-owned previews or metadata required for reliable display

Do not embed AI environments or model weights. Do not embed the original source by default. Loading legacy `.ssc.json` remains supported through migration.

Treat project archives as untrusted input. Validate the central directory before reading payloads: allow only normalized relative POSIX entry names from the documented schema; reject absolute paths, drive prefixes, backslashes, `.` or `..` components, duplicate names, links, and unexpected entry types. Enforce at most 20,000 entries, an 8 MiB `project.json`, 256 MiB per stored entry, and 4 GiB total declared uncompressed archive data. Validate each decoded tile as RGBA PNG with width and height no greater than 16,384, no more than 64 million pixels per tile, and no more than two billion decoded tile pixels per project. Stream or read explicitly named entries without extracting arbitrary archive paths.

### Paths and fingerprints

Store a relative source path when possible and retain enough fingerprint metadata to verify a relocated or replaced source. If automatic relative and absolute resolution fail, offer Locate Source. Never silently accept a different file with the same name.

### Atomicity and recovery

Write a complete ZIP project to a temporary sibling on the same volume, close and reopen it through the full validator, preserve one bounded backup of the previous valid save, flush the new file as supported by the platform, then replace the target with an atomic same-volume file replacement. Track dirty state and prompt before open, load, close, or exit would discard changes. A recovery flow detects an interrupted temporary save or valid backup and never merges entries from two generations.

### Legacy project import

Legacy `.ssc.json` files contain crop metadata and settings but not tile pixels, so import requires locating and fingerprinting the referenced source. If the source is unavailable or materially different, metadata can be inspected but tile migration is blocked until the correct source is located.

When the source is available, offer two explicit paths:

- Legacy-compatible import reconstructs bucket tile snapshots with a migration-only renderer matching the old per-tile algorithm closely enough to preserve the old bucket representation, then saves those pixels into `.sscproj`. Corrected sheet assembly applies after migration, so this is not a promise to reproduce an old exported sheet's repeated-alpha bug.
- Reprocess with the new pipeline previews and creates snapshots from a newly approved source revision.

Pixel-identical save/reload guarantees apply to `.sscproj` snapshots. They do not apply to legacy metadata before a migration path has successfully produced and persisted snapshots.

### Cache policy

Processed source revisions and mattes are regenerable caches keyed by source fingerprint, engine/model version and checksum, processing recipe version, and normalized settings. Cache entries live outside Git and use an index with size, last access, and validity metadata. Users can inspect cache usage, set a limit, and clear regenerable data without deleting project bucket snapshots or installed models.

Revisions expose Ready, Regenerable, and Unavailable states. Clearing a processed-source cache never prevents viewing or exporting persisted bucket snapshots. A missing cached revision is Regenerable only when the verified source, exact engine adapter, exact model checksum, and required runtime remain available. Otherwise extraction, revision comparison, and tile refresh from that revision are disabled with actions to locate the source, reinstall the exact model/runtime when still available, or create a distinct new revision with a currently available model. Regeneration never silently substitutes a newer model or changed source. Removing a model lists affected revisions before confirmation but does not remove project snapshots.

## Interface Direction

The user is an indie game developer or artist who needs visual confidence, repeatability, and control. The interface should feel like a technical sprite workstation rather than an opaque one-click effect.

Domain concepts include the source sheet, tile grid, crop frame, transparency checkerboard, alpha matte, source revision, model package, and GPU job.

The color world uses graphite or neutral work surfaces, a clear transparency checkerboard, cyan selection and primary interaction states, violet mask overlays, green success, amber warnings, and red errors. Magenta is not a primary application accent because it is a common source background.

The signature element is a compact source comparison and revision strip:

```text
Original | Alpha Mask | Transparent Result | Before/After    Revision 3 / Smart Solid
```

### Main source controls

- Engine and installed model
- Auto or manual background selection
- Transparent and foreground thresholds
- Edge softness and despill
- Pixel-art mode
- Preview quality and Preview Region
- Apply to Source
- Revert to Original
- Revision selector

Move source-background controls into their own task section instead of mixing them with tile and sheet geometry. Keep advanced cleanup and chunking collapsed by default.

### Job presentation

Use a nonmodal job strip with stage, progress, backend, elapsed time, Cancel, and structured warning access. Prevent conflicting source operations while allowing inspection and other safe UI actions.

### Revision completion

After successful processing, display that a new candidate revision is ready while the previous revision remains active. Present Compare, Activate Revision, and Discard Candidate actions. After explicit activation, state that existing bucket tiles were not changed and present Compare, Apply to Selected Tiles, and Apply to All Tiles. Revision-difference status must use text or icons as well as color.

### Model Manager

Use compact rows or cards displaying installation state, model/runtime sizes, speed/quality class, CPU/GPU support, memory estimate, license, and Install/Update/Repair/Uninstall controls. Never initiate a model download from merely selecting an unavailable engine.

## Error Handling and Diagnostics

Define stable error categories for validation, missing model, incompatible runtime, download, checksum, installation, worker protocol, worker crash, CUDA initialization, out of memory, cancellation, source mismatch, cache corruption, project migration, disk full, and export.

Each error provides a concise user action and preserves technical details in structured logs. Logs exclude source-image pixels and model inputs by default. Diagnostic export contains versions, manifests, provider availability, relevant settings, sanitized paths, and recent errors.

## Verification Strategy

### Asset corpus

Maintain representative fixtures for crisp pixel art, antialiased sprites, thin structures, hair/fur, soft shadows, translucent effects, foreground colors similar to the background, existing source transparency, multiple subjects, compressed backgrounds, and large sheets.

### Test layers

- Pure unit tests for color conversion, thresholds, connectivity, morphology, alpha combination, despill, premultiplied scaling, dilation, cache keys, validation, and migrations.
- Golden-image tests for mattes, RGBA results, tile placement, sheet placement, and final PNGs.
- Project round-trip tests proving identical bucket pixels after reload.
- Worker protocol tests using fake providers, progress, cancellation, malformed messages, timeout, and crash recovery.
- Download tests using a fake server for resume, checksum mismatch, interruption, unavailable network, incompatible manifest, and disk full.
- Simulated CUDA discovery, initialization, out-of-memory, smaller-chunk retry, and CPU fallback tests.
- Optional marked tests on a real NVIDIA GPU for supported provider profiles.
- PySide6 interaction tests for preview/apply behavior, successful candidate processing without automatic activation, explicit activation, candidate rejection, stable buckets, compare/update actions, Model Manager states, dirty prompts, and undo/redo.
- Large-source tests for bounded memory, disk-backed mattes, cancellation, cache cleanup, and preview responsiveness.
- End-to-end tests covering source open, processing, extraction, project save/reload, and transparent PNG export.

### Acceptance criteria

- A background engine is invoked once per source revision and never during normal tile extraction.
- Existing bucket tiles do not change without an explicit, confirmed command.
- Reloaded projects reproduce identical bucket PNG pixels.
- Semitransparent pixel alpha survives source, tile, and sheet placement unchanged unless an intentional matte operation changes it.
- Exact Key is deterministic and binary.
- Smart Solid protects disconnected, background-like foreground regions.
- Transparent-edge RGB dilation never changes alpha, runs after the last tile transform, and its hidden RGB survives individual-tile and sheet PNG round trips.
- On the reference test workstation, event-loop probe latency during processing, installation, and export jobs remains at or below 100 ms at the 95th percentile and 250 ms maximum, excluding an acknowledged operating-system stall.
- Failed or cancelled jobs do not replace the active revision.
- Successful processing alone does not replace the active revision; only the explicit Activate Revision command does so.
- No AI framework or model file appears in the repository.
- Installed providers function offline.
- GPU failures fall back visibly and safely in Auto mode.
- Legacy project metadata remains readable; tile migration requires the matching source and one of the explicit legacy-compatible or new-pipeline paths.
- Exported assets are readable straight-alpha RGBA PNGs.

Built-in job cancellation updates the UI within 100 ms and reaches a cancelled terminal state within 2 seconds. An AI worker that cannot cancel cooperatively is terminated within 5 seconds, after which the previous revision remains active.

For a `W x H` source, the main process's incremental full-source processing peak, above its idle project baseline, must not exceed `12 * W * H + 512 MiB` on the large-source benchmark. Each AI manifest records a measured warm-model baseline and maximum worker working set for its reference chunk; the worker must stay within their sum plus 15 percent on the same profile. Any provider that cannot meet its declared limit fails preflight or reduces its chunk rather than attempting an unbounded allocation.

Quality benchmarks use foreground/matte pixel error and boundary F-score against versioned ground truth. Smart Solid must improve mean boundary F-score by at least five percentage points and reduce mean alpha absolute error by at least 20 percent versus the current RGB-threshold implementation on the solid-background corpus, without regressing the protected similar-color subset. Each AI adapter must match its pinned upstream reference output within the adapter's documented numeric tolerance, and common post-processing must not reduce mean boundary F-score by more than one percentage point unless its halo/despill metric improves by an approved larger margin. AI timing is reported per model, image size, and hardware rather than enforcing one universal inference time.

## Delivery Sequence

1. Correct repeated-alpha placement and add regression tests.
2. Add premultiplied-alpha scaling and transparent RGB dilation tests.
3. Split source, tile, sheet, and preference settings; extract application services from `MainWindow`.
4. Add immutable sources, source revisions, cached previews, explicit Apply to Source, and stable bucket snapshots.
5. Implement Exact Key and the complete Smart Solid pipeline.
6. Introduce `.sscproj` schema v2, legacy migration, portable source resolution, atomic save, dirty state, recovery, and session undo/redo.
7. Add general job orchestration, cancellation, structured errors, and large-source chunking.
8. Add Model Manager manifests, managed environment creation, verified downloads, repair, update, uninstall, and offline state.
9. Integrate rembg-supported ONNX models with validated CUDA and CPU execution.
10. Integrate BEN2 ONNX with memory preflight, chunking, warm-up, and fallback.
11. Add explicit comparison and selected/all bucket revision updates.
12. Harden export, diagnostics, dependency locks, documentation, benchmark corpus, and release gates.

Each step must preserve a runnable application and pass the relevant existing and new tests before the next begins.

## Out of Scope

- Bundling model weights or complete AI environments in Git.
- Requiring an NVIDIA GPU for core application use.
- Automatic mutation of bucket tiles when a source revision changes.
- Silent model installation or download.
- Blocking models based on license category.
- Persistent cross-session undo history.
- Cloud inference or required accounts.
- A packaged standalone installer in this iteration; the design should not prevent one later.

## Reference Implementations and Runtime Documentation

- [rembg](https://github.com/danielgatis/rembg)
- [BEN2 model files](https://huggingface.co/PramaLLC/BEN2/tree/main)
- [BEN paper](https://arxiv.org/html/2501.06230)
- [ONNX Runtime CUDA Execution Provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)
- [ONNX Runtime installation](https://onnxruntime.ai/docs/install/)
- [PyTorch CUDA availability](https://docs.pytorch.org/docs/main/generated/torch.cuda.is_available.html)
- [PyMatting](https://github.com/pymatting/pymatting)
- [OpenCV Python packages](https://github.com/opencv/opencv-python)
- [scikit-image color conversion](https://scikit-image.org/docs/stable/api/skimage.color.html)
- [Godot texture importer](https://docs.godotengine.org/en/stable/classes/class_resourceimportertexture.html)

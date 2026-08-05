# Source-Level Background Removal Implementation Plan

## Status

Ready for implementation. This plan implements the approved [source-level background-removal architecture](../specs/2026-08-05-source-background-removal-architecture-design.md).

## Outcome

The application will process a source image once into a reviewable transparent-source revision, extract stable tile snapshots from that revision, and export correct straight-alpha PNG assets. Exact Key and Smart Solid will work without AI. rembg and BEN2 will be explicit, optional downloads installed into isolated user-data environments with validated NVIDIA CUDA and automatic CPU fallback.

The plan also fixes the correctness, responsiveness, persistence, dependency, diagnostics, and test gaps found during the repository audit.

## Execution Rules

- Keep the application runnable and the existing grid workflow intact after every task.
- Use test-first changes for algorithms, persistence, worker messages, downloads, and migrations.
- Do not download AI packages or weights during normal tests.
- Store test AI behavior in fakes and tiny synthetic fixtures; real model tests are opt-in.
- Never place runtime environments, weights, processed sources, or user caches inside Git.
- Commit each numbered task separately after its focused and regression tests pass.
- Avoid large module moves until compatibility adapters are in place.
- Treat cancellation, disk-full, corrupt input, missing source, and missing model as normal tested states.
- Preserve legacy `.ssc.json` loading throughout the migration.

## Baseline and Known Constraints

- Current branch at planning time: `dev`.
- Core tests observed: 25 passing; 15 PySide6 tests skipped in the available bundled test runtime because PySide6 was not installed there.
- The repository virtual environment identifies itself as Python 3.14.2 but cannot currently be executed from the available Codex sandbox. Recreate it if that also occurs outside the sandbox.
- Current rembg documentation and package metadata disagree on Python 3.14 support, while current ONNX Runtime GPU publishes Windows CPython 3.14 wheels. AI runtime work therefore begins with a locked compatibility probe rather than assuming the host interpreter works.
- The standalone packaged installer remains out of scope. Source execution and managed optional environments are in scope.

## Milestones

| Milestone | Tasks | Exit condition |
|---|---:|---|
| A. Correct pixels | 1-3 | Alpha survives tile/sheet placement; scaling and hidden RGB are game-safe. |
| B. Source workflow | 4-9 | Background removal runs once per source revision; the UI previews, creates, and explicitly activates candidates. |
| C. Reliable projects | 10-12 | Stable tile snapshots, safe `.sscproj`, migration, undo, recovery, and responsive previews work. |
| D. Optional AI | 13-17 | Model Manager, isolated workers, rembg, BEN2, CUDA validation, and CPU fallback work without repository bloat. |
| E. Release hardening | 18-20 | Export, diagnostics, locks, documentation, quality gates, and full regression tests pass. |

## Task 1: Establish a reproducible test and package foundation

### Files

- Create `pyproject.toml`.
- Create `sprite_sheet_cleaner/tests/helpers/image_assertions.py`.
- Create `sprite_sheet_cleaner/tests/fixtures/backgrounds/README.md`.
- Create small synthetic PNG fixtures under `sprite_sheet_cleaner/tests/fixtures/backgrounds/`.
- Create `.github/workflows/tests.yml`.
- Modify `sprite_sheet_cleaner/requirements.txt`.
- Modify `sprite_sheet_cleaner/README.md`.

### Work

1. Declare the core package, supported Python range, test discovery, and an `ai` test marker without adding AI packages to core dependencies.
2. Keep PySide6, Pillow, NumPy, pytest, and development/build tools in explicit groups instead of one unbounded list.
3. Add image helpers for exact RGBA comparison, alpha-only comparison, hidden-RGB inspection, boundary F-score, and alpha mean absolute error.
4. Add tiny fixtures covering binary pixel art, antialiased edges, existing alpha, thin details, similar foreground/background colors, soft shadows, and multi-sprite borders.
5. Configure UI tests to use Qt's offscreen platform and fail rather than silently skip in the supported development environment.
6. Run core/UI CI on the supported source Python matrix without installing any optional AI runtime; keep real-AI jobs manual or separately opt-in.
7. Record the baseline test result and document how to create a supported environment.

### Verification

```powershell
python -m unittest discover -s sprite_sheet_cleaner\tests -v
python -m pytest sprite_sheet_cleaner\tests -q
python -m compileall sprite_sheet_cleaner
```

### Commit

`test: establish image quality and UI test foundation`

## Task 2: Fix repeated alpha multiplication immediately

### Files

- Modify `sprite_sheet_cleaner/app/core/image_processor.py`.
- Modify `sprite_sheet_cleaner/app/core/sheet_builder.py`.
- Modify `sprite_sheet_cleaner/tests/test_image_processor.py`.
- Modify `sprite_sheet_cleaner/tests/test_sheet_builder.py`.

### Work

1. Add failing tests using a pixel such as `(100, 50, 25, 128)`.
2. Assert tile placement preserves the complete RGBA tuple.
3. Assert sheet placement preserves it a second time instead of producing alpha 64 or 16.
4. Replace `paste(image, position, image)` with direct RGBA placement for non-overlapping tile/sheet copying.
5. Keep an explicit helper for true alpha compositing so future code cannot reintroduce ambiguous paste-mask behavior.
6. Add PNG round-trip coverage for the semitransparent pixel.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_image_processor.py sprite_sheet_cleaner\tests\test_sheet_builder.py -q
python -m pytest sprite_sheet_cleaner\tests -q
```

### Commit

`fix: preserve alpha through tile and sheet placement`

## Task 3: Make scaling and transparent-edge RGB game-safe

### Files

- Create `sprite_sheet_cleaner/app/core/alpha_ops.py`.
- Create `sprite_sheet_cleaner/tests/test_alpha_ops.py`.
- Modify `sprite_sheet_cleaner/app/core/image_processor.py`.
- Modify `sprite_sheet_cleaner/app/core/export_manager.py`.

### Work

1. Implement straight-to-premultiplied conversion using sufficiently wide numeric types.
2. Resize premultiplied color and alpha consistently, then safely unpremultiply only where alpha is nonzero.
3. Implement bounded RGB dilation into zero-alpha pixels without changing alpha.
4. Run dilation after the final tile resize, padding, and canvas placement.
5. Preserve prepared hidden RGB during sheet assembly; never dilate across atlas-cell boundaries.
6. Add tests for zero alpha, low alpha, opaque pixels, no divide-by-zero, no alpha changes, no neighboring-cell contamination, and PNG round trips.
7. Switch `scale_to_settings` to the premultiplied implementation.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_alpha_ops.py sprite_sheet_cleaner\tests\test_image_processor.py sprite_sheet_cleaner\tests\test_sheet_builder.py -q
```

### Commit

`fix: add premultiplied scaling and output rgb bleed`

## Task 4: Split settings and stop global reprocessing signals

### Files

- Create `sprite_sheet_cleaner/app/models/source_processing_settings.py`.
- Create `sprite_sheet_cleaner/app/models/tile_settings.py`.
- Create `sprite_sheet_cleaner/app/models/sheet_settings.py`.
- Create `sprite_sheet_cleaner/app/models/user_preferences.py`.
- Modify `sprite_sheet_cleaner/app/models/app_settings.py`.
- Modify `sprite_sheet_cleaner/app/widgets/settings_panel.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.
- Modify `sprite_sheet_cleaner/tests/test_settings_panel.py`.
- Modify `sprite_sheet_cleaner/tests/test_project_model.py`.

### Work

1. Introduce validated dataclasses for the four approved settings domains.
2. Retain `AppSettings` as a temporary compatibility facade for existing project data and tests.
3. Add explicit migration between flat legacy keys and the new nested representation.
4. Emit scoped signals: source-preview settings, tile geometry, selection geometry, and sheet layout.
5. Remove `_settings_changed` behavior that synchronously calls `reprocess_tiles`.
6. Ensure linked tolerance controls emit one logical preview change.
7. Ensure changing sheet rows cannot invalidate a source preview and changing a source threshold cannot rebuild the bucket.
8. Preserve current Match Grid behavior and legacy `match_sheet_to_selection` migration.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_settings_panel.py sprite_sheet_cleaner\tests\test_project_model.py sprite_sheet_cleaner\tests\test_main_window.py -q
```

### Commit

`refactor: split settings and scope change events`

## Task 5: Introduce domain models for sources, revisions, and snapshots

### Files

- Create `sprite_sheet_cleaner/app/models/source_asset.py`.
- Create `sprite_sheet_cleaner/app/models/source_revision.py`.
- Create `sprite_sheet_cleaner/app/models/tile_snapshot.py`.
- Create `sprite_sheet_cleaner/app/models/project_document.py`.
- Create `sprite_sheet_cleaner/app/services/source_repository.py`.
- Create `sprite_sheet_cleaner/tests/test_source_repository.py`.
- Modify `sprite_sheet_cleaner/app/models/tile_item.py`.
- Modify `sprite_sheet_cleaner/app/core/project_model.py`.

### Work

1. Model the immutable original, active revision, optional completed candidate, and regenerable cache state.
2. Add source fingerprints based on content plus dimensions; do not rely only on names or timestamps.
3. Give every revision and tile a stable UUID.
4. Make `TileSnapshot` record its revision, crop rectangle, tile settings, content hash, and exact RGBA pixels or project asset reference.
5. Keep `TileItem` as a UI compatibility adapter while widgets migrate.
6. Enforce the state rule: successful processing creates a candidate; only an explicit command activates it.
7. Ensure rejection, failure, and cancellation leave the prior active revision untouched.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_source_repository.py sprite_sheet_cleaner\tests\test_project_model.py -q
```

### Commit

`feat: model immutable sources revisions and tile snapshots`

## Task 6: Define the engine contract and source-processing service

### Files

- Create `sprite_sheet_cleaner/app/engines/base.py`.
- Create `sprite_sheet_cleaner/app/engines/exact_key.py`.
- Create `sprite_sheet_cleaner/app/engines/postprocess.py`.
- Create `sprite_sheet_cleaner/app/services/source_processing_service.py`.
- Create `sprite_sheet_cleaner/tests/test_background_engine_contract.py`.
- Create `sprite_sheet_cleaner/tests/test_source_processing_service.py`.
- Modify `sprite_sheet_cleaner/app/core/image_processor.py`.
- Modify `sprite_sheet_cleaner/app/core/project_model.py`.

### Work

1. Define immutable engine descriptors, normalized settings, preview requests, progress events, cancellation tokens, and `MatteResult`.
2. Require engines to return a single-channel matte plus structured metadata rather than final tile images.
3. Implement Exact Key as the deterministic binary baseline.
4. Add shared post-processing that multiplies the matte by original alpha and returns straight RGBA.
5. Build deterministic cache keys from source fingerprint, engine/model identity, recipe version, and normalized settings.
6. Change normal tile extraction to crop the active processed source; it must never call an engine.
7. Add a counting fake engine and prove one source apply followed by many tile extractions performs one engine call.
8. Keep a migration-only legacy tile renderer isolated from the new extraction path.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_background_engine_contract.py sprite_sheet_cleaner\tests\test_source_processing_service.py sprite_sheet_cleaner\tests\test_project_model.py -q
```

### Commit

`feat: add source processing engines and one-pass extraction`

## Task 7: Implement Smart Solid background removal

### Files

- Create `sprite_sheet_cleaner/app/engines/smart_solid.py`.
- Create `sprite_sheet_cleaner/app/core/color_math.py`.
- Create `sprite_sheet_cleaner/app/core/matte_ops.py`.
- Create `sprite_sheet_cleaner/tests/test_color_math.py`.
- Create `sprite_sheet_cleaner/tests/test_matte_ops.py`.
- Create `sprite_sheet_cleaner/tests/test_smart_solid.py`.
- Modify `sprite_sheet_cleaner/app/core/background_detector.py`.
- Modify core dependency declarations if `opencv-python-headless` wins the benchmark.

### Work

1. Benchmark NumPy-only operations against `opencv-python-headless` for Lab conversion, connected components, and morphology. Prefer headless OpenCV if it materially improves large-sheet performance; do not add GUI OpenCV beside PySide6.
2. Replace a single dominant border bin with visible-border sampling, robust clustering/median estimation, and confidence output.
3. Convert sRGB to Lab and implement the documented perceptual distance with published reference-value tests.
4. Generate a soft matte from transparent and foreground thresholds.
5. Restrict uncertain removal to components connected to the image border.
6. Add optional one-pixel close/open cleanup, disabled by pixel-art mode.
7. Implement adjustable edge despill/foreground-color reconstruction in linear light.
8. Multiply the result by existing source alpha.
9. Add golden tests for all corpus categories and record the current hard-threshold baseline.
10. Meet the approved quality gate: at least +5 percentage points mean boundary F-score and 20% lower alpha MAE on the solid-background corpus without regressing the similar-color subset.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_color_math.py sprite_sheet_cleaner\tests\test_matte_ops.py sprite_sheet_cleaner\tests\test_smart_solid.py -q
```

### Commit

`feat: add perceptual connected smart background removal`

## Task 8: Build the source-background UI and comparison viewer

### Files

- Create `sprite_sheet_cleaner/app/widgets/source_background_panel.py`.
- Create `sprite_sheet_cleaner/app/widgets/source_comparison_strip.py`.
- Create `sprite_sheet_cleaner/app/widgets/job_strip.py`.
- Create `sprite_sheet_cleaner/app/controllers/source_processing_controller.py`.
- Create `sprite_sheet_cleaner/tests/test_source_background_panel.py`.
- Create `sprite_sheet_cleaner/tests/test_source_processing_controller.py`.
- Modify `sprite_sheet_cleaner/app/widgets/source_viewer.py`.
- Modify `sprite_sheet_cleaner/app/widgets/settings_panel.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.

### Work

1. Move all background controls out of the tile/sheet settings form.
2. Add engine, model, color detection, two thresholds, edge softness, despill, pixel-art mode, preview quality, and advanced cleanup controls.
3. Add Original, Alpha Mask, Transparent Result, and Before/After modes.
4. Add debounced preview-region requests with monotonically increasing request IDs; ignore stale completions.
5. Add Apply to Source, Compare, Activate Revision, Discard Candidate, Revert to Original, and revision selection.
6. Prove that Apply completion alone does not activate a candidate.
7. Remove the current automatic tolerance increase and automatic destructive processing on image open.
8. Keep background detection as a suggestion with confidence and an explicit apply action.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner\tests\test_source_background_panel.py sprite_sheet_cleaner\tests\test_source_processing_controller.py sprite_sheet_cleaner\tests\test_main_window.py -q
```

### Commit

`feat: add non destructive source background workflow`

## Task 9: Add cancellable jobs, progress, and large-source chunking

### Files

- Create `sprite_sheet_cleaner/app/jobs/job_types.py`.
- Create `sprite_sheet_cleaner/app/jobs/qt_job_controller.py`.
- Create `sprite_sheet_cleaner/app/core/chunking.py`.
- Create `sprite_sheet_cleaner/app/storage/matte_buffer.py`.
- Create `sprite_sheet_cleaner/tests/test_job_controller.py`.
- Create `sprite_sheet_cleaner/tests/test_chunking.py`.
- Create `sprite_sheet_cleaner/tests/test_large_source_processing.py`.
- Modify `sprite_sheet_cleaner/app/services/source_processing_service.py`.
- Modify `sprite_sheet_cleaner/app/widgets/job_strip.py`.

### Work

1. Run built-in preview/apply work outside the UI thread using a bounded executor appropriate for Qt.
2. Define queued, running, cancelling, cancelled, failed, and succeeded states.
3. Implement cooperative cancellation checks between chunks and algorithm stages.
4. Add overlap geometry and deterministic matte stitching.
5. Use disk-backed `uint8` matte storage above a tested source-size threshold.
6. Commit candidate files atomically only after dimensions, mode, checksum, and completion validate.
7. Add event-loop probes and meet p95 100 ms/max 250 ms latency.
8. Meet the two-second built-in cancellation deadline and approved memory formula.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_job_controller.py sprite_sheet_cleaner\tests\test_chunking.py sprite_sheet_cleaner\tests\test_large_source_processing.py -q
```

### Commit

`feat: add cancellable chunked source jobs`

## Task 10: Implement safe `.sscproj` persistence and stable snapshots

### Files

- Create `sprite_sheet_cleaner/app/storage/project_archive.py`.
- Create `sprite_sheet_cleaner/app/storage/project_schema.py`.
- Create `sprite_sheet_cleaner/app/storage/project_migrations.py`.
- Create `sprite_sheet_cleaner/app/services/project_service.py`.
- Create `sprite_sheet_cleaner/tests/test_project_archive.py`.
- Create `sprite_sheet_cleaner/tests/test_project_service.py`.
- Create `sprite_sheet_cleaner/tests/test_project_migrations.py`.
- Modify `sprite_sheet_cleaner/app/core/project_model.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.

### Work

1. Implement the ZIP layout with `project.json` and `tiles/<uuid>.png`.
2. Validate entry names, duplicates, types, size/count limits, PNG dimensions, decoded-pixel totals, and schema before use.
3. Stream known entries instead of arbitrary extraction.
4. Persist exact RGBA tile snapshots and prove pixel-identical reload.
5. Store project-relative source paths when possible plus absolute fallback and content fingerprint.
6. Add Locate Source for missing/mismatched paths.
7. Save to a same-volume sibling temporary file, reopen through the validator, preserve one backup, and atomically replace.
8. Add Save, Save As, project path tracking, dirty state, and close/open/load prompts.
9. Define Ready, Regenerable, and Unavailable revision behavior while always allowing persisted bucket export.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_project_archive.py sprite_sheet_cleaner\tests\test_project_service.py sprite_sheet_cleaner\tests\test_project_migrations.py -q
```

### Commit

`feat: add safe portable project bundles`

## Task 11: Add explicit legacy import paths

### Files

- Create `sprite_sheet_cleaner/app/services/legacy_project_importer.py`.
- Create `sprite_sheet_cleaner/app/core/legacy_v1_renderer.py`.
- Create `sprite_sheet_cleaner/app/widgets/legacy_import_dialog.py`.
- Create `sprite_sheet_cleaner/tests/test_legacy_project_importer.py`.
- Modify `sprite_sheet_cleaner/app/storage/project_migrations.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.

### Work

1. Parse legacy metadata without treating it as a new bundle.
2. Require the matching source before reconstructing missing pixels.
3. Offer legacy-compatible snapshot reconstruction or a previewed new-pipeline reprocess.
4. Keep the old alpha/paste behavior only inside the migration helper; never expose it to new projects.
5. Explain that corrected sheet assembly can differ from an old exported sheet containing repeated-alpha loss.
6. Save successful imports immediately as `.sscproj` only after user confirmation.
7. Add corrupted JSON, missing source, changed source, old match-grid keys, and successful import tests.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_legacy_project_importer.py sprite_sheet_cleaner\tests\test_project_migrations.py -q
```

### Commit

`feat: add explicit legacy project migration`

## Task 12: Add undoable bucket revision updates and incremental previews

### Files

- Create `sprite_sheet_cleaner/app/commands/command_stack.py`.
- Create `sprite_sheet_cleaner/app/commands/bucket_commands.py`.
- Create `sprite_sheet_cleaner/app/widgets/tile_comparison_dialog.py`.
- Create `sprite_sheet_cleaner/app/services/preview_service.py`.
- Create `sprite_sheet_cleaner/tests/test_command_stack.py`.
- Create `sprite_sheet_cleaner/tests/test_bucket_revision_updates.py`.
- Modify `sprite_sheet_cleaner/app/widgets/bucket_panel.py`.
- Modify `sprite_sheet_cleaner/app/widgets/final_preview.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.

### Work

1. Add session undo/redo for delete, clear, duplicate, rename, reorder, selected update, and all-tile update.
2. Mark tiles whose revision differs from the active source using text/icon as well as color.
3. Preview old and candidate tile pixels before replacement.
4. Make multi-tile updates atomic and retain prior snapshots in the command.
5. Cache thumbnails by tile content hash.
6. Build a scaled final preview from cached thumbnails; build the full-resolution sheet only for export or an explicit full preview.
7. Preserve bucket selection and avoid broad list reconstruction when one tile changes.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_command_stack.py sprite_sheet_cleaner\tests\test_bucket_revision_updates.py sprite_sheet_cleaner\tests\test_main_window.py -q
```

### Commit

`feat: add undoable snapshot updates and cached previews`

## Task 13: Build the Model Manager foundation

### Files

- Create `sprite_sheet_cleaner/app/runtime/paths.py`.
- Create `sprite_sheet_cleaner/app/runtime/manifest.py`.
- Create `sprite_sheet_cleaner/app/runtime/registry.py`.
- Create `sprite_sheet_cleaner/app/runtime/download_manager.py`.
- Create `sprite_sheet_cleaner/app/runtime/environment_manager.py`.
- Create `sprite_sheet_cleaner/app/runtime/manifests/schema.json`.
- Create `sprite_sheet_cleaner/app/widgets/model_manager_dialog.py`.
- Create `sprite_sheet_cleaner/tests/test_runtime_paths.py`.
- Create `sprite_sheet_cleaner/tests/test_runtime_manifest.py`.
- Create `sprite_sheet_cleaner/tests/test_download_manager.py`.
- Create `sprite_sheet_cleaner/tests/test_environment_manager.py`.

### Work

1. Resolve application data through `platformdirs`, never a repository-relative model folder.
2. Define manifest identity, adapter version, model URLs/hashes/sizes, package lock artifacts/hashes, Python compatibility, license, memory guidance, and provider support.
3. Implement explicit Downloading, Verifying, Installing, Testing, Ready, Update Available, Incompatible, and Repair Needed states.
4. Use temporary/resumable downloads and atomic verified finalization.
5. Create provider environments with the source-running interpreter only when the manifest supports it.
6. Install packages with `pip --require-hashes` from a platform/Python-specific lock.
7. Place ownership markers in managed leaf directories.
8. Before repair/uninstall, enforce canonical descendant containment and reject roots, symlinks, junctions, reparse points, unknown files, and unmarked directories.
9. Use fake HTTP and fake package installers for normal tests.
10. Display sizes, compatibility, memory, license, and actions; never install when a user merely selects an engine.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_runtime_paths.py sprite_sheet_cleaner\tests\test_runtime_manifest.py sprite_sheet_cleaner\tests\test_download_manager.py sprite_sheet_cleaner\tests\test_environment_manager.py -q
```

### Commit

`feat: add verified isolated model manager`

## Task 14: Define and harden the isolated AI worker protocol

### Files

- Create `sprite_sheet_cleaner/app/ai_protocol/messages.py`.
- Create `sprite_sheet_cleaner/app/ai_protocol/client.py`.
- Create `sprite_sheet_cleaner/ai_worker/main.py`.
- Create `sprite_sheet_cleaner/ai_worker/provider_base.py`.
- Create `sprite_sheet_cleaner/tests/fakes/fake_ai_worker.py`.
- Create `sprite_sheet_cleaner/tests/test_ai_protocol.py`.
- Create `sprite_sheet_cleaner/tests/test_ai_worker_lifecycle.py`.
- Modify `sprite_sheet_cleaner/app/jobs/qt_job_controller.py`.

### Work

1. Define versioned JSON messages for hello/capabilities, load, infer, progress, cancel, release, result, error, and shutdown.
2. Use one JSON message per framed line and keep large pixels in verified job-owned temporary files.
3. Reject unknown protocol versions, IDs, operations, paths, dimensions, and output types.
4. Never deserialize pickle.
5. Keep a compatible worker alive for model reuse and restart it after protocol failure, timeout, repair, or explicit memory release.
6. Request cooperative cancellation, then terminate an unresponsive worker within five seconds.
7. Add crash, malformed JSON, stale response, path escape, partial output, timeout, and restart tests.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_ai_protocol.py sprite_sheet_cleaner\tests\test_ai_worker_lifecycle.py -q
```

### Commit

`feat: add versioned isolated ai worker protocol`

## Task 15: Add compute discovery, CUDA validation, and fallback

### Files

- Create `sprite_sheet_cleaner/ai_worker/capabilities.py`.
- Create `sprite_sheet_cleaner/ai_worker/onnx_provider.py`.
- Create `sprite_sheet_cleaner/tests/test_compute_capabilities.py`.
- Create `sprite_sheet_cleaner/tests/test_compute_fallback.py`.
- Modify `sprite_sheet_cleaner/app/models/user_preferences.py`.
- Modify `sprite_sheet_cleaner/app/widgets/model_manager_dialog.py`.

### Work

1. Add Auto, NVIDIA GPU, and CPU preferences.
2. Discover NVIDIA devices/free memory through a validated NVIDIA tool or library when available, but do not treat enumeration as readiness.
3. Query ONNX Runtime execution providers and create a real warm-up session.
4. Record provider name, device, free/total VRAM, runtime versions, and warnings.
5. Compare free memory with manifest guidance before a job.
6. In Auto mode, attempt CUDA, retry with a smaller chunk on out-of-memory, then recreate the session on CPU.
7. In forced NVIDIA mode, report failure unless the user separately enables fallback.
8. Surface the backend actually used and the fallback reason.
9. Cover no GPU, missing DLL, provider absent, warm-up failure, OOM, reduced chunk, CPU retry, and forced-mode behavior with fakes.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_compute_capabilities.py sprite_sheet_cleaner\tests\test_compute_fallback.py -q
```

### Commit

`feat: add validated cuda selection and cpu fallback`

## Task 16: Integrate rembg without hidden downloads

### Files

- Create `sprite_sheet_cleaner/app/runtime/manifests/rembg-onnx.json`.
- Create platform/Python hashed package locks referenced by that manifest.
- Create `sprite_sheet_cleaner/ai_worker/rembg_provider.py`.
- Create `sprite_sheet_cleaner/tests/test_rembg_provider.py`.
- Create `sprite_sheet_cleaner/tests/ai/test_rembg_smoke.py`.
- Modify `sprite_sheet_cleaner/app/engines` registry code.

### Work

1. Run a compatibility spike against the actual supported Python versions, including this workspace's Python 3.14.2.
2. Pin a rembg release and compatible ONNX Runtime CPU/GPU profiles only after installation, import, session, and inference smoke tests pass.
3. Start with a small representative model list: BiRefNet General Lite as the normal fallback candidate, ISNet Anime as a sprite/anime candidate, and U2Net as a baseline.
4. Have Model Manager download every weight explicitly and verify its SHA-256 before marking Ready.
5. Set `U2NET_HOME` to the managed model directory and preflight the exact expected filename/checksum before importing or creating a session.
6. Prevent inference from invoking rembg's automatic downloader; a missing file must return Repair Required without network access.
7. Request matte-only output, normalize it to the common contract, and reuse sessions.
8. Test against a network-denying fake to prove installed inference is offline.
9. If the pinned rembg package cannot run on Python 3.14, mark that manifest incompatible and document the supported interpreter; do not silently mutate the core environment. Direct ONNX engines remain available.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_rembg_provider.py -q
python -m pytest sprite_sheet_cleaner\tests\ai\test_rembg_smoke.py -q -m ai
```

### Commit

`feat: add explicit offline rembg provider`

## Task 17: Integrate BEN2 Base through ONNX

### Files

- Create `sprite_sheet_cleaner/app/runtime/manifests/ben2-base-onnx.json`.
- Create `sprite_sheet_cleaner/ai_worker/ben2_provider.py`.
- Create `sprite_sheet_cleaner/tests/test_ben2_provider.py`.
- Create `sprite_sheet_cleaner/tests/ai/test_ben2_smoke.py`.
- Create `sprite_sheet_cleaner/benchmarks/benchmark_background_models.py`.
- Modify the engine/model registry and Model Manager UI.

### Work

1. Pin the BEN2 ONNX model URL, exact checksum, preprocessing, 1024 input contract, normalization, and output conversion from the upstream implementation.
2. Show download/installed size and measured RAM/VRAM guidance. Treat the reported roughly 4.5 GB VRAM usage for 1024 inference as guidance to remeasure, not a universal guarantee.
3. Use the common overlapping chunker for sheets that would lose detail when reduced to one 1024 input.
4. Warm the CUDA session, run memory preflight, reduce chunk where valid, and fall back to CPU in Auto mode.
5. Blend overlaps deterministically and test seams with synthetic objects crossing chunk boundaries.
6. Match pinned upstream reference output within a documented numeric tolerance before applying common cleanup.
7. Benchmark BEN2 against Smart Solid and selected rembg models on the game-asset corpus; retain native PyTorch BEN2 as a later option only if it demonstrates a meaningful advantage.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_ben2_provider.py sprite_sheet_cleaner\tests\test_chunking.py -q
python -m pytest sprite_sheet_cleaner\tests\ai\test_ben2_smoke.py -q -m ai
```

### Commit

`feat: add ben2 onnx source background provider`

## Task 18: Harden export, errors, cache management, and diagnostics

### Files

- Create `sprite_sheet_cleaner/app/errors.py`.
- Create `sprite_sheet_cleaner/app/services/diagnostics_service.py`.
- Create `sprite_sheet_cleaner/app/storage/cache_index.py`.
- Create `sprite_sheet_cleaner/app/widgets/cache_settings_dialog.py`.
- Create `sprite_sheet_cleaner/tests/test_export_manager.py`.
- Create `sprite_sheet_cleaner/tests/test_cache_index.py`.
- Create `sprite_sheet_cleaner/tests/test_diagnostics.py`.
- Modify `sprite_sheet_cleaner/app/core/export_manager.py`.
- Modify `sprite_sheet_cleaner/app/main_window.py`.

### Work

1. Add stable error categories and user actions for validation, source mismatch, model/runtime, network, checksum, worker, CUDA, OOM, cancellation, cache, project, disk, and export failures.
2. Preflight output capacity, dimensions, mode, writable space, filename collisions, and overwrite decisions.
3. Stage individual and sheet outputs, validate PNG reopen/mode/dimensions, then finalize and report cleanup status.
4. Add cache size/last-access/validity indexing and enforce a user-configurable limit.
5. Never evict project-owned tile snapshots or installed models through cache cleanup.
6. Show revisions affected before a model uninstall.
7. Add structured rolling logs and sanitized diagnostic export without source pixels.
8. Replace repeated generic modal exceptions with actionable messages plus a Details path.

### Verification

```powershell
python -m pytest sprite_sheet_cleaner\tests\test_export_manager.py sprite_sheet_cleaner\tests\test_cache_index.py sprite_sheet_cleaner\tests\test_diagnostics.py -q
```

### Commit

`feat: harden export cache and diagnostics`

## Task 19: Lock dependencies and update source-user documentation

### Files

- Modify `pyproject.toml`.
- Create core/dev lock files using the selected lock tool.
- Finalize runtime-specific hashed locks under `sprite_sheet_cleaner/app/runtime/locks/`.
- Modify `sprite_sheet_cleaner/requirements.txt` as a compatibility entry point.
- Modify `sprite_sheet_cleaner/README.md`.
- Modify root `README.md`.
- Modify `sprite_sheet_cleaner/build.py` only for a source/build smoke check; do not expand packaged-installer scope.

### Work

1. Pin and hash reproducible core and development dependencies for the supported Python matrix.
2. Keep optional AI packages exclusively in runtime locks/manifests.
3. Document source setup, supported Python versions, test commands, user-data locations, cache behavior, model sizes, CUDA/CPU fallback, offline behavior, and uninstall.
4. Document that no model or runtime is stored in the repository.
5. Add troubleshooting for Python compatibility, CUDA DLLs, worker logs, model repair, missing sources, legacy migration, and cache clearing.
6. Add a repository check that fails if common model extensions, runtime directories, or oversized unapproved assets enter Git.
7. Update `.gitignore` for any local benchmark output while keeping manifests and tiny fixtures tracked.

### Verification

```powershell
python -m pip check
python -m compileall sprite_sheet_cleaner
python -m pytest sprite_sheet_cleaner\tests -q
git ls-files | Select-String -Pattern '\.(onnx|pth|pt|safetensors)$'
```

The final command must return no model-weight files.

### Commit

`docs: lock source setup and optional ai runtimes`

## Task 20: Execute release gates and close the audit

### Files

- Create `sprite_sheet_cleaner/benchmarks/README.md`.
- Create `sprite_sheet_cleaner/benchmarks/benchmark_large_source.py`.
- Create `sprite_sheet_cleaner/tests/test_end_to_end_workflow.py`.
- Update `Plan/BuildStatus.md`.
- Update the approved design document only if implementation discoveries require an explicitly reviewed amendment.

### Work

1. Run the complete core/UI suite with PySide6 installed and zero unexpected skips.
2. Run end-to-end original → preview → candidate → explicit activation → extraction → `.sscproj` save/reload → individual/sheet export.
3. Verify bucket pixels are identical after reload.
4. Run Smart Solid quality metrics against the frozen current-algorithm baseline.
5. Run large-source memory, event-loop latency, cancellation, and disk-backed matte gates.
6. Run fake download/worker/CUDA failure suites offline.
7. On a real NVIDIA machine, install rembg and BEN2 through Model Manager, verify checksums, validate CUDA, process the corpus, force an OOM/fallback scenario where safe, and verify CPU fallback.
8. Disconnect networking and prove installed-model inference still works without download attempts.
9. Uninstall/repair runtimes and models and verify containment protections.
10. Clear caches and verify bucket viewing/export remains available while unavailable revision actions are disabled correctly.
11. Test legacy import with available, missing, and changed sources.
12. Inspect exported sprites against checkerboard, dark, light, and colored backgrounds and in a game-engine texture importer.
13. Update the build status with measured RAM, VRAM, timing, quality, remaining limitations, and exact tested versions.

### Verification

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest sprite_sheet_cleaner\tests -q
python sprite_sheet_cleaner\benchmarks\benchmark_large_source.py
python sprite_sheet_cleaner\benchmarks\benchmark_background_models.py
git status --short
```

### Commit

`test: complete background removal release gates`

## Final Acceptance Checklist

- [ ] Alpha is not multiplied during tile or sheet placement.
- [ ] Scaling uses premultiplied alpha and output-stage hidden-RGB dilation.
- [ ] Exact Key and Smart Solid create a full-source candidate once.
- [ ] Successful processing requires explicit activation.
- [ ] Extraction never invokes a background engine.
- [ ] Existing bucket snapshots never change implicitly.
- [ ] Selected/all snapshot updates are previewed and undoable.
- [ ] `.sscproj` reloads identical tile pixels and rejects unsafe archives.
- [ ] Legacy JSON migration is explicit and source-dependent.
- [ ] Project saves are atomic, portable, recoverable, and dirty-state aware.
- [ ] Long work is asynchronous, cancellable, progress-reporting, and memory-bounded.
- [ ] Full previews and thumbnails are incremental/cached.
- [ ] Model Manager performs only explicit, verified installations outside Git.
- [ ] Repair/uninstall cannot escape marked managed directories.
- [ ] rembg cannot download weights during inference.
- [ ] BEN2 and rembg use validated CUDA when possible and visible CPU fallback otherwise.
- [ ] Installed models run offline.
- [ ] Exports are validated straight-alpha RGBA PNGs with game-safe edges.
- [ ] Dependencies are locked and no model weights are tracked.
- [ ] Core, UI, migration, failure, performance, quality, and real-GPU gates pass.

## Recommended Implementation Branching

Use one integration branch such as `codex/source-background-removal`, with milestone pull requests or review checkpoints after Tasks 3, 9, 12, 17, and 20. Do not begin optional AI integration until the source-revision workflow and project snapshot format are stable; otherwise model-specific behavior will leak into the old per-tile architecture.

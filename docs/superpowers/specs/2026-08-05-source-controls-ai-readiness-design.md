# Source Controls and AI Readiness Design

## Goal

Make source-background controls visually consistent and make optional AI engines understandable from setup through first use. An installed engine must never disappear into a silent state: the application must say whether it is installing, verifying, ready, awaiting a restart, or in need of repair.

This design complements the separately approved bucket-preview exit design.

## Product direction

The relevant product domain is sprite sources, transparency, color-key tolerance, alpha thresholds, matte generation, model weights, isolated runtimes, compute backends, and reviewable candidates. The interface keeps the existing system palette: source colors and keyed magenta remain content, checkerboard grays and alpha black/white remain canvas cues, and platform semantic colors communicate ready, warning, and error states.

The signature interaction is a visible readiness path tied directly to each optional engine:

**Install → Verify → Select → Run → Review candidate**

This replaces three defaults that caused the current confusion:

- a hidden Tools-menu installer becomes visible setup beside the engine controls;
- a silent download becomes named installation stages with a final outcome;
- a file-marker-only “ready” assumption becomes a real isolated-worker health check.

The panel stays compact and technical. It uses the existing spacing, platform typography, and border treatment rather than adding a new color or card system.

## Approaches considered

1. **Verified readiness with run on demand (selected).** Install and health-check immediately, select the engine when ready, and let the user explicitly run it on the current source. This is proactive without unexpectedly starting a costly image job.
2. **Completion messages only.** Show a popup and restart guidance after download. This is easier, but it can report success when imports, model loading, or the compute backend are broken.
3. **Start every installed model at application launch.** This maximizes eager readiness but increases launch time and keeps unnecessary worker/model memory alive.

## Threshold slider controls

`Exact tolerance`, `Transparent threshold`, and `Foreground threshold` use the same control pattern as the existing lower `Tolerance` field:

- a horizontal slider fills the available width;
- a compact editable numeric spin box sits on the right;
- slider and spin box remain bidirectionally synchronized;
- existing ranges and defaults remain unchanged;
- changing either member emits one logical `settingsChanged` notification;
- disabling the panel during a processing job disables both members of every pair.

The existing spin-box attributes remain available to minimize compatibility risk. New `*_slider` attributes expose the sliders for synchronization and testing. A small private helper creates the three identically spaced rows so their layout cannot drift.

## Source-panel AI setup

The Source Background panel gains a compact `AI model setup` area directly beneath the engine selector. It contains one status row for rembg and one for BEN2. Each row shows the engine name, current state, and a context action:

| State | Status text | Action |
| --- | --- | --- |
| Not installed | `Not installed` | `Install…` |
| Model only | `Runtime required` | `Install runtime…` |
| Installing | current stage and percentage when available | disabled progress action |
| Verifying | `Checking model and runtime…` | disabled |
| Ready | `Ready · CPU` or `Ready · CUDA` | `Manage…` |
| Restart required | `Installed · restart required` | `Restart app…` |
| Repair required | concise failure summary | `Repair…` |

The panel also includes one short instruction: optional engines require both a model and an isolated runtime; after verification, select the engine and run it to create a reviewable candidate.

The two setup buttons open the existing model manager with the matching runtime preselected. The manager remains the single owner of installation logic, download-size/license disclosure, progress, cancellation/closing rules, and detailed diagnostics.

## Model-manager installation flow

The primary manager action is renamed to `Install model + runtime (recommended)`. A secondary `Model only` action remains available for advanced/offline preparation, but it never marks the engine ready.

The installation task reports explicit stages:

1. downloading the verified model;
2. creating the isolated environment;
3. installing pinned packages;
4. verifying the worker, provider, model, and compute backend.

The dialog stays open at completion and presents a persistent summary rather than replacing it during list refresh. On success it says, for example:

`rembg is ready on CPU. It is now available in Source Background.`

On failure it shows the failed stage, a concise reason, `Retry`, and `View details`/copyable diagnostics. Partial installation remains represented accurately as `Model only` or `Repair required`; it is never labeled ready.

## Health-check contract

Disk markers remain useful installation evidence but are not sufficient for readiness. The worker protocol gains a health-check request carrying the provider ID, model ID/path, and compute preference. The isolated worker must:

- import the requested provider;
- validate that the expected model exists and is non-empty;
- initialize the provider/session far enough to prove ONNX Runtime and the chosen backend can load the model;
- return the effective backend and warnings;
- return a structured failure when imports, DLLs, packages, model files, or backend initialization fail.

The health check runs off the UI thread. After installation it runs immediately. On later application launches, installed runtimes are checked asynchronously; the source panel shows `Checking…` until each result arrives. A verified engine is then registered with `SourceProcessingService` and enabled in the engine selector.

Health-check workers may exit after verification. The inference worker remains lazy and starts when the user runs the engine, avoiding permanent RAM/VRAM use. In this design, `Ready` means verified and callable—not continuously consuming resources.

## Successful activation and first run

When setup and verification succeed during the current session:

1. `MainWindow` registers the engine immediately; a restart is not the normal path.
2. The engine is enabled and selected in Source Background.
3. The existing `Process` button becomes `Run rembg` or `Run BEN2` for an AI selection.
4. If a source image is open, the run button is enabled and the panel says that running will create a reviewable candidate.
5. If no source is open, the panel says `Ready—open a source image to run rembg`.
6. Processing remains user-triggered. Completion continues into the existing candidate review flow rather than silently activating or rewriting bucket tiles.

Exact Key and Smart Solid retain the neutral `Process` label.

## Restart fallback

Because engines run in isolated processes and are registered dynamically, installation should normally take effect without restarting. `Restart required` is reserved for a detected activation failure that is plausibly caused by the current process holding stale runtime state; generic health-check failures use `Repair required` instead.

`Restart app…` must warn the user to save current work before closing. It starts a replacement application process only after confirmation and only reports success if the replacement launch succeeds. If safe automatic restart cannot be guaranteed, the action becomes `Restart instructions…` and clearly tells the user to save, close, and reopen the app.

## Ownership and component boundaries

- `SourceBackgroundPanel` renders linked threshold controls and per-provider readiness states. It emits setup/manage and run requests but performs no downloads or probes.
- `ModelManagerDialog` coordinates user-approved installation, stage progress, retry, and diagnostics. It does not directly mutate the source image.
- `RuntimeRegistry` remains the authority for manifests, managed paths, marker validation, and disk installation state.
- The isolated worker owns provider imports, session/model initialization, and backend probing.
- `MainWindow` coordinates asynchronous readiness results, engine registration, selection, status messages, and the existing candidate-processing action.

Provider IDs remain stable (`rembg`, `ben2`) while runtime IDs remain manifest-specific (`rembg-onnx`, `ben2-base-onnx`). Mapping is always read from manifest metadata rather than guessed from labels.

## Error handling

- Closing the manager during an active install is blocked or requires explicit cancellation confirmation; it must not make the install look successful.
- A failed checksum remains a download failure and leaves no final model file.
- A package-install failure preserves diagnostics and offers repair without deleting unrelated user data.
- A health-check timeout terminates its worker and becomes `Repair required` with retry.
- CUDA failure under `Auto` may return a visible warning and a verified CPU fallback. CUDA-only failure is not silently downgraded.
- Selecting an engine whose readiness was lost disables Run and returns it to `Checking…` or `Repair required`.
- All status text is meaningful without relying on color alone.

## Verification

Automated coverage should include:

- all three slider/spin pairs synchronize in both directions and emit one logical settings change;
- paired controls retain current ranges/defaults and disable together during a job;
- rembg and BEN2 setup actions emit the correct provider/runtime selection;
- the model manager reports each installation stage and keeps the final message visible;
- model-only installation does not enable an engine;
- successful health check reports CPU/CUDA, enables and selects the engine, and updates the Run label;
- worker import, model, backend, timeout, and package-install failures map to actionable states;
- Auto visibly falls back to CPU while CUDA-only remains a failure;
- installed engines are checked asynchronously at startup without blocking the UI;
- a ready engine with no source gives open-source guidance;
- a ready engine with a source runs only after explicit user action and creates a candidate;
- restart is not requested after ordinary successful hot registration;
- restart/repair guidance never claims an engine is ready prematurely.

Run focused widget, runtime, worker-protocol, and main-window tests, followed by the full suite.

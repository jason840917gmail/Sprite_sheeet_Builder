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

Installation is deliberately non-cancellable because the current download, virtual-environment, and package-install operations are not safely interruptible. While any installation stage is active:

- the dialog Close button and window close action are disabled;
- attempts to close the dialog explain that setup must finish or fail first;
- application shutdown is refused with the same explanation;
- each operation has a bounded timeout so this policy cannot trap the user indefinitely: network connect/read timeout, environment-creation timeout, package-install timeout, and health-check timeout;
- timeouts become ordinary failed-stage results and restore Close/Retry controls.

The model download and environment/package installation both use per-attempt managed staging directories. The model checksum and runtime ownership are verified in staging before promotion. A failed staging directory is removed only after ownership/path validation. If a new model succeeds but the environment fails, the stable state is accurately reported as `Model only` only when that model was safely promoted for a previously absent runtime; a failed repair never replaces the prior working model/runtime.

Timeout enforcement lives inside the underlying operation, not only around the `QRunnable`. A network timeout closes and joins the response/read operation before staging cleanup. Environment and package commands run as owned subprocess groups; on timeout the app terminates the full descendant process tree, waits for it to exit, validates/cleans staging, and only then emits the failed-stage result. Retry and Close stay disabled until the task confirms that no network operation, subprocess, or descendant can continue writing.

## Health-check contract

Disk markers remain useful installation evidence but are not sufficient for readiness. The worker protocol gains these concrete messages:

```text
request:
  protocol_version: 1
  message_type: "health_check"
  request_id: non-empty unique string
  provider_id: "rembg" | "ben2"
  model_id: manifest model identifier
  model_path: absolute managed model path
  compute: "auto" | "cuda" | "cpu"

success:
  protocol_version: 1
  message_type: "health_result"
  request_id: copied from request
  provider_id: copied from request
  model_id: copied from request
  status: "ready"
  backend: "cuda" | "cpu"
  warnings: list of strings

failure:
  protocol_version: 1
  message_type: "error"
  request_id: copied from request
  provider_id: copied when validated
  error_code: stable code
  message: actionable summary
```

Stable health error codes are `provider_import_failed`, `model_missing`, `model_invalid`, `runtime_unavailable`, `backend_unavailable`, `initialization_failed`, `health_timeout`, and `protocol_error`. The worker preserves the request ID on every response, including exception paths. Unknown IDs or response types are protocol errors and cannot mark an engine ready.

For a health request, the isolated worker must:

- import the requested provider;
- validate that the expected model exists and is non-empty;
- initialize the provider/session far enough to prove ONNX Runtime and the chosen backend can load the model;
- return the effective backend and warnings;
- return a structured failure when imports, DLLs, packages, model files, or backend initialization fail.

The health check runs off the UI thread with a fixed timeout. Its dedicated worker process is closed in `finally` after success, failure, timeout, stale result, or application shutdown. A timeout forcibly terminates that health worker before emitting `health_timeout`.

One `OptionalEngineCoordinator` owned by `MainWindow` is the sole owner of readiness state and in-flight probes. Readiness is keyed by `(runtime_id, compute_preference)`, and only one probe for a key may run at once. Both startup discovery and `ModelManagerDialog` request work through this coordinator; the dialog never runs a second private probe. The manager emits installation completion to the coordinator, then observes the coordinator's staged/readiness signals for its selected runtime. `MainWindow` observes those same signals to update the source panel and register engines. Each probe carries a generation token so a late result from an older compute preference or repaired runtime is discarded and its worker closed.

After installation the coordinator verifies immediately. On later application launches, installed runtimes are checked asynchronously; the source panel shows `Checking…` until each result arrives. A verified engine is then registered with `SourceProcessingService` and enabled in the engine selector.

Health-check workers must exit after verification. The inference worker remains lazy and starts when the user runs the engine, avoiding permanent RAM/VRAM use. In this design, `Ready` means verified and callable—not continuously consuming resources.

## Compute preference

The Source Background panel's Compute selection is the authoritative preference. Opening model setup initializes the manager to that value. Readiness for Auto, CUDA, or CPU is not interchangeable:

- changing Compute invalidates the displayed readiness result for installed AI engines;
- the selected AI engine remains visible but Run is disabled while the coordinator re-verifies it;
- a new result is accepted only if its compute preference and generation still match the panel;
- `Auto` may verify as CUDA or CPU and must display the effective backend plus any fallback warning;
- `CUDA only` fails with `backend_unavailable` if CUDA cannot initialize;
- `CPU only` constructs the provider with CPU-only execution providers.

rembg and BEN2 use the same backend-selection contract in health checks and inference. The rembg worker must no longer ignore `compute`: CPU passes only `CPUExecutionProvider`; CUDA requires and initializes `CUDAExecutionProvider`; Auto uses the shared selection/fallback rules. The backend verified for a given preference is the backend shown to the user and used to construct that inference-engine registration.

## Successful activation and first run

When setup and verification succeed during the current session:

1. `MainWindow` registers the engine immediately; a restart is not the normal path.
2. The engine is enabled and selected in Source Background.
3. The existing `Process` button becomes `Run rembg` or `Run BEN2` for an AI selection.
4. If a source image is open, the run button is enabled and the panel says that running will create a reviewable candidate.
5. If no source is open, the panel says `Ready—open a source image to run rembg`.
6. Processing remains user-triggered. Completion continues into the existing candidate review flow rather than silently activating or rewriting bucket tiles.

Exact Key and Smart Solid retain the neutral `Process` label.

## Truthful progress action

The source `Process` / `Run rembg` / `Run BEN2` button becomes a `ProgressActionButton`. In its idle state it remains an ordinary accessible push button. While a source-processing job owns it, the button rejects duplicate activation and paints a semantic green progress layer behind live stage text. The existing Cancel button remains the explicit cancellation control.

The progress treatment is hybrid because rembg and BEN2 each execute their core inference as one opaque ONNX operation. Neither model exposes a trustworthy percentage inside `session.run`, so the UI must not invent one:

- `Preparing source…` uses an indeterminate moving green band while the input is converted and written;
- `Loading rembg…` / `Loading BEN2…` is driven by the real provider/session initialization event;
- `Running rembg…` / `Running BEN2…` remains indeterminate only while the ONNX inference call is active;
- `Finalizing candidate…` begins only after inference returns and the result is being validated/applied/stored;
- `Candidate ready` becomes a solid 100% state only after `SourceRepository.create_candidate` succeeds;
- failure clears the green layer and restores the correct idle action while showing the existing actionable error;
- cancellation changes the label to `Cancelling…`, remains indeterminate until the worker is actually stopped, and resets only after the job emits its terminal cancelled signal.

A determinate fill is permitted only when an operation reports measured completed/total work units. Stage boundaries are not converted into arbitrary percentages. Thus animation means “this verified phase is currently active,” while a numerical/fill percentage means measured work.

The progress component uses a named semantic `success_progress` token with light/dark variants and contrast-tested foreground text. It preserves the platform button border, radius, focus ring, typography, and size so it feels like the existing technical controls. The animation timer runs only while a live job owns the button. Accessible name/value text mirrors the phase and measured percentage, and the label remains sufficient without color or motion.

Completion is a real, paintable state rather than an immediately overwritten assignment. On the matching completed signal, the button enters `complete`, shows a solid 100% fill and `Candidate ready`, updates its accessible value, and remains non-interactive for a minimum 750 ms. A single-shot timer then restores the engine-specific idle label only if its job/generation still owns the button. Returning to the event loop before the timer fires guarantees at least one paint opportunity. Failure and cancelled states reset without displaying 100%.

## Source-job progress contract

Core jobs use a typed progress update rather than treating every event as a float:

```text
SourceJobProgress:
  job_id: unique source-job identifier
  phase: "preparing" | "loading_model" | "inference" | "finalizing" | "complete"
  message: user-facing stage text
  mode: "indeterminate" | "determinate"
  value: omitted for indeterminate; measured 0.0 through 1.0 for determinate
```

`QtJobController` forwards this object unchanged. `MainWindow` accepts updates only from the currently active source job, preventing late messages from an earlier cancelled/replaced job from moving the button.

Every job signal carries the same ID, not only progress:

```text
progress(job_id, SourceJobProgress)
completed(job_id, result)
failed(job_id, error)
cancelled(job_id)
```

`MainWindow` filters all four signal types against the active job ID. A stale progress or terminal signal is ignored and cannot clear `_source_job`, change candidate state, dispose an engine, or reset the button. The one inference request made for a source job uses that job ID as its worker `request_id`; every intermediate and terminal worker message must preserve it.

AI worker inference may emit zero or more intermediate protocol messages before its terminal result:

```text
progress:
  protocol_version: 1
  message_type: "progress"
  request_id: copied from infer request
  phase: "loading_model" | "inference"
  mode: "indeterminate" | "determinate"
  value: present only for measured determinate work
  message: non-empty stage text
```

`AIWorkerClient.request` reads and validates progress messages until it receives one terminal `result` or `error`, forwarding matching progress to the source job. Mismatched request IDs, invalid modes/values, or progress after a terminal response are protocol errors. Providers emit `loading_model` immediately before session initialization, `inference` immediately before the real model call, and a terminal result only after output validation/saving. The service itself emits `preparing`, `finalizing`, and `complete` around actual source conversion, matte application, and candidate storage.

The current blocking `readline()` is replaced by a client-owned reader thread feeding a bounded response queue. The request loop polls that queue with a short timeout so it can observe cancellation and request deadlines even when the worker emits no output. On cancellation/timeout it terminates the worker process, closes all pipe handles, joins the process and reader thread, drains/discards queued messages, and only then returns the terminal cancellation/error. `IsolatedAIWorkerEngine` clears its cached client on this path; a later run must create a fresh process and reader. Normal result/error/shutdown paths also close or retain resources only according to explicit client ownership, never leaving a blocked reader behind.

For AI cancellation, the request loop observes the job cancellation token. Cancellation terminates and joins the isolated inference-worker process, removes temporary input/output files through the existing temporary-directory lifetime, and only then emits cancelled. Exact Key and Smart Solid re-check cancellation between their real processing phases and never store a candidate after cancellation.

Candidate persistence uses an atomic cancellation/commit boundary. The job context owns a lock-protected `begin_commit()` operation. `SourceProcessingService` checks cancellation before finalization and again immediately before persistence, then calls `begin_commit()`:

- if cancellation already won, `begin_commit()` returns false and no candidate is written;
- if commit wins, later cancellation requests cannot reclassify the job as cancelled;
- `create_candidate` then either succeeds and yields exactly one completed signal, or raises and yields exactly one failed signal.

`QtJobController` bases the terminal outcome on this context state rather than checking a bare cancellation flag after the operation returns. This prevents a late click on Cancel after successful persistence from hiding a real candidate behind a false cancelled result. A per-job terminal guard ensures completed, failed, and cancelled are mutually exclusive.

## Restart fallback

Because engines run in isolated processes and are registered dynamically, installation should normally take effect without restarting. `Restart required` is reserved for a detected activation failure that is plausibly caused by the current process holding stale runtime state; generic health-check failures use `Repair required` instead.

`Restart app…` must warn the user to save current work before closing. It starts a replacement application process only after confirmation and only reports success if the replacement launch succeeds. If safe automatic restart cannot be guaranteed, the action becomes `Restart instructions…` and clearly tells the user to save, close, and reopen the app.

## Ownership and component boundaries

- `SourceBackgroundPanel` renders linked threshold controls and per-provider readiness states. It emits setup/manage and run requests but performs no downloads or probes.
- `ModelManagerDialog` coordinates user-approved installation, stage progress, retry, and diagnostics. It does not directly mutate the source image.
- `RuntimeRegistry` remains the authority for manifests, managed paths, marker validation, and disk installation state.
- `OptionalEngineCoordinator` deduplicates asynchronous health checks, owns compute-keyed readiness/generation state, and publishes the single authoritative result stream to the dialog and main window.
- The isolated worker owns provider imports, session/model initialization, and backend probing.
- `MainWindow` coordinates asynchronous readiness results, engine registration, selection, status messages, and the existing candidate-processing action.

Provider IDs remain stable (`rembg`, `ben2`) while runtime IDs remain manifest-specific (`rembg-onnx`, `ben2-base-onnx`). Mapping is always read from manifest metadata rather than guessed from labels.

`MainWindow` also owns inference-engine replacement. Replacing, disabling, or repairing a registered engine closes the old `IsolatedAIWorkerEngine` so its child process cannot leak. If a source-processing job is active, the current engine remains owned by that job and the new readiness result is queued; replacement and old-engine disposal occur only after the job completes, fails, or is cancelled. Application shutdown stops accepting probe results, terminates all health workers, refuses to close while a model installation is active, lets the existing source job follow its current cancellation lifecycle, and closes every registered optional inference engine.

Installation/repair promotion obeys the same active-job boundary. A staged model or runtime for the engine serving the current source job is marked `Update ready—waiting for current job`; it cannot replace final files while that job or its inference worker may read them. After the job settles, `MainWindow` closes the old engine, the coordinator atomically promotes the verified staging pair, and only then registers the replacement. For an existing managed runtime, promotion uses an ownership-validated backup/swap/restore transaction so failure preserves the previous working pair. Recovery markers make an interrupted swap detectable on the next launch.

Shutdown ordering is strict: block shutdown while installation/promotion is active; otherwise stop accepting new work, request cancellation of an active source job, wait for its terminal signal, close its and all other inference engines, terminate and join all health workers, and only then allow the window to close. No engine is closed while a job can still call it.

## Error handling

- Closing the manager or application during an active install is blocked until the bounded task finishes or fails; it must not make the install look successful.
- A failed checksum remains a download failure and leaves no final model file.
- A package-install failure preserves diagnostics and offers repair without deleting unrelated user data.
- A health-check timeout terminates its worker and becomes `Repair required` with retry.
- CUDA failure under `Auto` may return a visible warning and a verified CPU fallback. CUDA-only failure is not silently downgraded.
- Selecting an engine whose readiness was lost disables Run and returns it to `Checking…` or `Repair required`.
- All status text is meaningful without relying on color alone.
- Stale health results caused by compute changes, repairs, or shutdown are discarded without mutating engine availability.
- A staged repair cannot promote over files used by an active source job; failed or interrupted promotion restores the prior verified runtime.
- No timeout result enables Retry/Close until its network operation or complete subprocess tree has stopped and staging cleanup has finished.
- Source-job progress with a stale job or request ID is ignored/rejected and cannot change the active button.
- No source job displays 100% until candidate storage succeeds, and no opaque inference phase displays a fabricated percentage.
- Cancellation and candidate commit are atomic: cancellation before commit writes nothing, while cancellation after commit cannot replace completion.
- A cancelled/failed/completed source job emits exactly one ID-bearing terminal signal.

## Verification

Automated coverage should include:

- all three slider/spin pairs synchronize in both directions and emit one logical settings change;
- paired controls retain current ranges/defaults and disable together during a job;
- rembg and BEN2 setup actions emit the correct provider/runtime selection;
- the model manager reports each installation stage and keeps the final message visible;
- model-only installation does not enable an engine;
- successful health check reports CPU/CUDA, enables and selects the engine, and updates the Run label;
- Compute changes invalidate prior readiness, disable Run during re-verification, initialize setup with the panel preference, and reject stale results;
- rembg and BEN2 both honor Auto, CPU-only, and CUDA-only during health check and inference;
- worker import, model, backend, timeout, and package-install failures map to actionable states;
- Auto visibly falls back to CPU while CUDA-only remains a failure;
- installed engines are checked asynchronously at startup without blocking the UI;
- model-manager installation completion reaches `MainWindow` through the coordinator once, without a duplicate probe;
- dialog and application closing are blocked during download, environment creation, package installation, and verification, then restored after success/failure;
- every health-worker success, failure, timeout, and stale result closes the health process;
- replacing or repairing a running engine defers replacement until the active source job settles, then closes the old engine;
- model/runtime staging rejects unowned paths, removes failed attempts, promotes successful first installs, and preserves then safely replaces an existing managed pair;
- download, environment, package, and health timeouts leave no live operation or descendant capable of late writes before Retry/Close is enabled;
- an active source job prevents staging promotion, and shutdown waits for the job before closing its engine;
- a ready engine with no source gives open-source guidance;
- a ready engine with a source runs only after explicit user action and creates a candidate;
- the action button enters busy state with real preparing/loading/inference/finalizing messages and blocks duplicate runs;
- opaque model inference uses indeterminate green progress while measured work alone uses determinate fill;
- the button reaches 100% only after candidate persistence, then returns to the correct engine-specific idle label;
- failure and cancellation clear progress, preserve actionable status, and never create a candidate;
- AI cancellation terminates/joins the inference worker before the cancelled UI state settles;
- cancellation while a worker emits no output interrupts the reader, closes pipes, clears the cached client, and permits a fresh subsequent run;
- cancellation before/during finalization prevents persistence, while cancellation after the commit boundary preserves the completed candidate;
- stale, mismatched, malformed, and post-terminal progress messages cannot mutate the active job UI;
- stale completed, failed, and cancelled signals cannot clear or reset a newer active job;
- the solid 100% completion state receives a paint cycle, blocks duplicate activation during its hold, then restores the correct idle label after at least 750 ms;
- accessible name/value updates are verified for idle, every busy phase, cancelling, complete, failed, and cancelled transitions;
- progress text/value remains accessible without relying on green color or animation;
- restart is not requested after ordinary successful hot registration;
- restart/repair guidance never claims an engine is ready prematurely.

Run focused widget, runtime, worker-protocol, and main-window tests, followed by the full suite.

# Bucket Tile Preview Exit Design

## Goal

Let an image-source user return to the full source image after opening a bucket tile in the source viewer, without disturbing the existing source-selection workflow.

## Approaches considered

1. **Escape only.** Minimal state and keyboard-friendly, but not discoverable to mouse-only users.
2. **Second click only.** Keeps the interaction near the bucket tile, but provides no keyboard exit and can feel hidden.
3. **Escape and second click (selected).** Supports keyboard and pointer workflows with a small, predictable state change.

## Interaction design

- Clicking a bucket tile while no bucket preview is active displays that tile in the source viewer.
- Clicking a different bucket tile while previewing switches directly to that tile.
- Clicking the currently previewed bucket tile again restores the full source image.
- Pressing Escape while a bucket preview is active restores the full source image.
- Pressing Escape while no bucket preview is active retains its current behavior and clears the source selection.
- While a tile is previewed, the status bar names the tile and says that Escape or another click on the tile returns to the source.

No new button, color, or layout treatment is introduced. The interaction uses the existing bucket list, source viewer, and status bar.

## State and components

`MainWindow` owns the preview state because it already coordinates the bucket and source viewer. Replace the boolean-only state with an optional active bucket index, or add an index alongside the boolean. The state must distinguish these cases:

- no preview is active;
- tile N is active;
- a click targets tile N again;
- a click targets a different tile.

The existing bucket `tileClicked` signal remains unchanged. The existing Escape action remains the single shortcut entry point and becomes context-sensitive in `MainWindow`.

## Data flow

1. The bucket emits the clicked tile index.
2. `MainWindow` compares that index with the active preview index.
3. A matching index restores `source_image`; a different index displays the selected tile and records its index.
4. Escape checks preview state first. If a preview is active it restores the source and stops; otherwise it clears the source selection as it does today.
5. Any existing workflow that restores or replaces the source also clears the active preview index.

## Edge cases

- Invalid or stale tile indexes remain no-ops.
- Bucket previews remain image-source-only, matching current behavior.
- Restoring with no source image clears preview state safely and does not raise an error.
- Switching tools continues to restore the source through the shared restore helper.
- Bucket mutations must not leave a stale preview index active; existing refresh/mutation paths should either restore first or invalidate preview state.

## Verification

Automated tests should cover:

- first click opens a tile preview;
- clicking a different tile switches the preview;
- clicking the same tile twice restores the source;
- Escape restores the source when previewing;
- Escape still clears a source selection when not previewing;
- the status hint is present while previewing;
- invalid indexes do not change state.

Run the focused main-window tests, followed by the full test suite if the focused tests pass.

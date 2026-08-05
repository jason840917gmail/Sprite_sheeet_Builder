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

`MainWindow` owns the preview state because it already coordinates the bucket and source viewer. The canonical state is `_bucket_preview_index: int | None`; no separate preview boolean is retained. The state distinguishes these cases:

- no preview is active;
- tile N is active;
- a click targets tile N again;
- a click targets a different tile.

The existing bucket `tileClicked` signal remains unchanged. `SourceViewer` currently consumes Escape in `keyPressEvent`, so it will expose an Escape-request signal instead of owning the outcome. Both that signal and the window's existing Escape action delegate to one context-sensitive handler in `MainWindow`. This makes the result identical with the source viewer, bucket list, or another window control focused.

## Data flow

1. The bucket emits the clicked tile index.
2. `MainWindow` compares that index with the active preview index.
3. A matching index restores `source_image`; a different index displays the selected tile and records its index.
4. The shared Escape handler checks preview state first. If a preview is active it restores the source and stops; otherwise it clears the source selection as it does today.
5. Source replacement and every bucket mutation—delete, clear, duplicate, move, reorder, undo, and redo—call the shared restore operation before changing state. Restoration displays the full source and clears the active preview index as one operation, so the state cannot say “source” while a tile image remains displayed.
6. Restoration refreshes the normal source-view status. The tile name and exit hint are removed immediately.

## Edge cases

- Invalid or stale tile indexes remain no-ops.
- Bucket previews remain image-source-only, matching current behavior.
- Restoring with no source image clears preview state safely, refreshes normal status, and does not raise an error.
- Switching tools continues to restore the source through the shared restore helper.
- Bucket mutations and source replacements must restore the displayed full source and clear preview state atomically; clearing only the index is not sufficient.

## Verification

Automated tests should cover:

- first click opens a tile preview;
- clicking a different tile switches the preview;
- clicking the same tile twice restores the source;
- Escape restores the source when previewing;
- Escape still clears a source selection when not previewing;
- real Escape key events behave identically with the source viewer and bucket list focused;
- the status hint is present while previewing;
- the normal source status replaces the preview hint after Escape and same-tile restoration;
- delete, reorder, and undo while previewing restore the source before mutating the bucket;
- invalid indexes do not change state.

Run the focused main-window tests, followed by the full test suite if the focused tests pass.

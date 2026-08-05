# Paint Cursor, Clone Sampling, and Panel Restoration Design

## Goal

Make Paint Cleanup feel like a normal brush editor and keep the surrounding UI synchronized when the user changes tools.

## Interaction

- Paint mode hides the OS crosshair and shows a circular brush footprint centered under the pointer.
- The footprint uses the raw brush-size slider diameter in image pixels, scales with viewer zoom, clips at image edges, and hides when the pointer leaves the viewer or Paint mode ends. The blank OS cursor is restored on leave/tool exit.
- The brush-size slider sends value changes directly to SourceViewer, which updates the overlay without a tool switch.
- Clone Color Alt-click samples RGB from the current target, updates the Paint Color swatch and status text with the sampled hex value, and records the clone source point.
- If Clone Color has no source point yet, a normal first click is sample-only: it performs the same RGB/swatch/hex update, records clone origin, marks the press as consumed, and emits no drag/release painting event, stroke, candidate, or bucket undo. The next click-drag paints. Existing clone-stamp RGB copying and destination-alpha preservation remain unchanged.
- Clone origin resets on mode changes, target changes, and source/image replacement.
- Leaving Paint restores the Image settings panel for image sources or the active Video settings panel for video sources by setting `right_panel_stack` explicitly.

## State and safety

The cursor is a non-interactive scene overlay and never receives mouse events. Source Preview candidates and bucket undo behavior remain unchanged. Switching tools restores the existing source/bucket preview state safely.

## Verification

Add tests for OS cursor/overlay visibility, raw-diameter and zoom scaling, edge clipping, pointer leave/enter, clone sampling and swatch updates, sample-only first-click behavior, reset paths, and Image/Video `right_panel_stack` restoration after leaving Paint. Run full unittest discovery and compile checks.

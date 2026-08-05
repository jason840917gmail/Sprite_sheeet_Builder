# Paint Controls and Bucket Preview Design

## Goal

Make Paint Cleanup usable directly on bucket tiles and replace arrow-based numeric inputs with compact slider controls for brush and source-background thresholds.

## Interaction

- While the Paint tool is active, clicking a bucket tile selects it as the Paint target and displays that tile in the source viewer.
- A different bucket click switches the active Paint tile; clicking the same tile again keeps it active for continued editing. Returning to Source Preview or leaving Paint restores the source view through the existing tool-switch path; same-tile/Escape preview-exit behavior remains deferred to the separate bucket-preview-exit design.
- The Paint target dropdown remains available for switching back to Source Preview.
- Source Preview edits continue to produce review candidates; bucket edits remain undoable per completed stroke.

## Controls

- Paint brush size: horizontal slider, 1-512 image pixels, default 24, with a read-only pixel value label.
- Paint opacity: horizontal slider, 1-100%, default 100, with a read-only percentage value label.
- Source Background Exact tolerance: horizontal slider, 0-255, default 30, with a read-only value label.
- Transparent threshold: horizontal slider, 0-255, default 24, with a read-only value label.
- Foreground threshold: horizontal slider, 1-255, default 64, with a read-only value label.

Raw slider/control values and source-background threshold accessors remain integers. Slider `valueChanged` updates those values and labels, while existing validation (including threshold ordering) and processing behavior remain unchanged. The existing normalized `RetouchPanel.brush_opacity()` float API remains unchanged.

Selecting a bucket tile never activates, discards, or replaces a pending source candidate. Switching back to Source Preview continues to show that candidate.

## Verification

Add widget-level tests for slider ranges, defaults, value propagation, and label updates. Add a MainWindow regression test that clicking a bucket tile in Paint mode selects the bucket target, previews it, and permits a stroke that mutates the tile; verify the stroke is undoable and restores exact pixels. Verify source editing leaves the active source unchanged until explicit activation and that pending candidates survive target changes. Run the full unittest discovery and compile checks.

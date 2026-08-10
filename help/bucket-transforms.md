# Bucket Size and Tile Transforms

## Selection size versus output size

**Source selection** describes the cells on the original image. **Bucket / output tile** describes every final tile canvas. These values are deliberately independent.

Example:

```text
Source selection: 256 x 256
Bucket output:      64 x 64
Sheet grid:          8 x 8
Final PNG:         512 x 512
```

The bucket uses one output size for every tile. Individual tile resizing changes the visible content inside that canvas, not the cell size.

## On Add resize modes

- **Fit** preserves aspect ratio and keeps the whole sprite visible, adding transparent padding when needed.
- **Fit Down Only** behaves like Fit but never enlarges smaller content.
- **Fill / Crop** preserves aspect ratio, fills the available canvas, and crops overflow.
- **Stretch** fills both dimensions without preserving aspect ratio.
- **No Scale** centers at the source size and clips anything outside the output canvas.

Use **Smooth** resampling for painted sprites and **Nearest** for deliberate pixel-art edges.

Changing the project bucket dimensions updates all existing bucket tiles together. Undo restores the prior dimensions and exact tile snapshots.

## Rotate controls

1. Select a bucket tile.
2. Choose **Rotate** or press `R`.
3. Drag any orange corner or the orange center ring.
4. Drag the blue center dot when a different pivot is needed.
5. Hold `Shift` to snap in 15-degree increments.
6. Press Enter or **Apply Transform** to commit. Press Esc or **Cancel** to discard staged changes.

The transform panel also provides linked X/Y scale, a numeric angle, quick quarter/half turns, pivot reset, scale reset, Fit Content, Fill Canvas, and Fit Rotated.

The dashed pale rectangle is the fixed output canvas. A red transform outline and clipping message mean visible content crosses this boundary. Clipped pixels are transparent in the final tile; use Fit Rotated or reduce scale to keep them.

Transform previews always render from the unchanged editable base. Dragging back and forth therefore does not repeatedly rotate the previous preview and compound blur. Apply creates one undoable bucket change.

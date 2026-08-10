# Right Panel Guide

The right side of the window is organized from source processing to output review.

## Source Background

- **Engine** selects the remover. Exact Key is best for a known flat color; Smart Solid keeps connected foreground regions; rembg and BEN2 are optional downloaded AI engines. rembg/U2Net works best on one isolated tile or object, not a complete sprite sheet.
- **Compute** controls hardware selection. Auto tries NVIDIA CUDA and visibly falls back to CPU when CUDA is unavailable.
- **Background** shows the RGB key color. **Detect** samples the current source border and updates this color.
- **Exact tolerance** controls how close a pixel must be to the key color before it is removed.
- **Transparent threshold** makes very low-alpha pixels fully transparent.
- **Foreground threshold** keeps high-alpha pixels solid. Values between the two thresholds remain partially transparent for smoother edges.
- **Process** creates a reviewable candidate from the original source.
- **Activate** makes the reviewed candidate the source for future tile extraction.
- **To Bucket** applies the candidate to existing bucket tiles in one undoable operation.
- **Discard** removes the pending candidate and keeps the original active.
- **Cancel** stops a running background-removal job.

## Tile Background Processing

- The **Remove background** checkbox in **Settings** controls processing when new image tiles are added to the bucket.
- The adjacent **Tile remover** menu chooses **Exact Key** (the default), **Smart Solid**, or **rembg — U2Net (single tile)**.
- Example: choose **Exact Key** for a uniform purple backdrop such as `#6E0BF5`; choose **Smart Solid** when that color may also appear as an enclosed detail inside the sprite.
- With **rembg — U2Net** selected, add one image tile at a time. **Add All** and multi-tile selections are not supported because U2Net is intended for a single tile, not a full sprite sheet.
- Tile processing uses the selected remover automatically when the tile is added. Existing bucket tiles are not changed when this control changes.
- The tile **Background** color and **Tolerance** apply to Exact Key and Smart Solid; rembg uses its own model-based segmentation.

## Image or Video Tool

Image mode separates **Source selection** dimensions from **Bucket / output tile** dimensions. Select and Grid use the source size; every bucket tile, animation frame, sheet cell, individual export, and metadata rectangle uses the bucket size.

- **On Add resize** controls how source content enters the fixed bucket canvas: No Scale, Fit Down Only, Fit, Fill/Crop, or Stretch.
- **Resampling** chooses Smooth for painted/high-resolution assets or Nearest for pixel art.
- Changing the bucket dimensions resizes every existing bucket tile together and can be undone.
- A per-tile scale changes content inside the fixed bucket canvas. It never creates a differently sized sheet cell.

Video mode uses its shared frame output size as the bucket/output canvas and keeps the same fixed-size sheet rule.

## Bucket Tile Transform

Choose **Rotate** (`R`) with a bucket tile selected to open the transform panel.

- Drag an orange corner or the orange center ring to rotate around the pivot.
- Drag the blue center dot to move the pivot.
- Hold **Shift** while rotating to snap to 15-degree steps.
- Scale X/Y resizes the tile content inside the fixed output canvas. Link X/Y for uniform scaling.
- Use the numeric angle or the `-90`, `+90`, and `180` quick actions for exact turns.
- **Fit Rotated** reduces scale enough to keep the rotated visible content inside the output canvas.
- A red outline and `clipped` label warn that content crosses the output boundary.
- **Apply Transform** or Enter commits one undoable change. **Cancel** or Esc restores the exact committed tile.

Transforms use transparent fixed-size canvases. Entering Paint Cleanup on a transformed bucket tile bakes the committed appearance first, then makes each stroke undoable as usual.

## Paint Cleanup

Choose the **Paint** tool (`B`) to finish an imperfect removal without changing the immutable original source.

- **Source Preview** edits a review copy. Each completed stroke becomes a manual candidate; use **Activate** in Source Background when it is ready, or **Discard** to return to the active source.
- **Selected Bucket Tile** edits the currently selected tile directly. Each stroke is one undoable bucket change.
- **Erase** reduces alpha to make pixels transparent.
- **Paint Color** paints the chosen swatch into RGB and alpha; transparent pixels become visible according to brush opacity.
- **Clone Color** samples an RGB pixel with **Shift+left-click**, then paints that exact sampled color and alpha. Shift-click again at any time to replace the sample.
- **Brush size** is the diameter in image pixels; **Opacity** controls stroke strength.

## Bucket

The bucket is the ordered list of fixed-output-size tiles that will be written to the sheet. Each row shows its source crop and final output dimensions. Drag to reorder animation frames, or use the buttons to rename, duplicate, move, delete, and clear. **Undo** and **Redo** restore pixels, transforms, output-size changes, and video frame metadata.

## Final Tilesheet Preview

This preview shows the transparent output canvas, capacity, empty slots, and overflow. Use it to confirm the order and dimensions before exporting.

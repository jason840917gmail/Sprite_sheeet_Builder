# Right Panel Guide

The right side of the window is organized from source processing to output review.

## Source Background

- **Engine** selects the remover. Exact Key is best for a known flat color; Smart Solid keeps connected foreground regions; rembg and BEN2 are optional downloaded AI engines.
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

## Image or Video Tool

Image mode controls tile dimensions, selection grids, background removal, trimming, scaling, padding, anchor, and final sheet rows/columns. Video mode replaces those controls with frame range, sampling, output sizing, resize mode, and animation settings.

## Bucket

The bucket is the ordered list of tiles that will be written to the sheet. Drag to reorder animation frames, or use the buttons to rename, duplicate, move, delete, and clear. **Undo** and **Redo** restore bucket snapshots, including video frame metadata.

## Final Tilesheet Preview

This preview shows the transparent output canvas, capacity, empty slots, and overflow. Use it to confirm the order and dimensions before exporting.

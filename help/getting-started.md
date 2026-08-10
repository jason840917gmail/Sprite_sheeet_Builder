# Getting Started

## Image workflow

1. Choose **File > Open Image** and load a PNG, JPG, WebP, or BMP.
2. Set **Source selection** to the cell size on the original image. Set **Bucket / output tile** to the size every exported tile should use. For example, select at `256 x 256` and output at `64 x 64`.
3. Choose **On Add resize**: Fit preserves the whole sprite, Fill/Crop fills the canvas, Stretch forces both dimensions, and No Scale centers without resizing. Use **Nearest** resampling for pixel art.
4. Use **Select** to place a source-sized selection, or **Grid** to work with an evenly divided source sheet.
5. Review the source background settings. Background processing creates a candidate first, so the original remains safe.
6. Add selections to the bucket. You can rename, duplicate, reorder, delete, or clear tiles.
7. Select a bucket tile and press `R` for **Rotate**. Drag an orange corner or the center ring to rotate; drag the blue center dot to move the pivot. Press Enter to apply or Esc to cancel.
8. If an edge needs cleanup, press `B` for **Paint Cleanup**. Choose a source review copy or a selected bucket tile, then use Erase, Paint Color, or Clone Color.
9. Check the transparent sheet in **Final Tilesheet Preview**.
10. Export the sheet or individual tiles as PNG files.

## Safe background-removal workflow

The safest order is **Process → inspect → Activate**. Activating a candidate changes the source used for future extraction; existing bucket tiles are not silently replaced. Use **To Bucket** when you want to apply a candidate to existing tiles without making it the global active source.

## Projects

Use **Save Project** to keep tile snapshots and settings. The `.sscproj` format stores exact RGBA tile images in an archive; JSON projects store portable source paths and regenerate tiles from the source image.

# Getting Started

## Image workflow

1. Choose **File > Open Image** and load a PNG, JPG, WebP, or BMP.
2. Set the tile width and height in the right-side image settings. Enable **Sym** when both dimensions should stay equal.
3. Use **Select** to place a tile-sized selection, or **Grid** to work with an evenly divided source sheet.
4. Review the source background settings. Background processing creates a candidate first, so the original remains safe.
5. Add selections to the bucket. You can rename, duplicate, reorder, delete, or clear tiles.
6. If an edge needs cleanup, press `B` for **Paint Cleanup**. Choose a source review copy or a selected bucket tile, then use Erase, Paint Color, or Clone Color.
7. Check the transparent sheet in **Final Tilesheet Preview**.
8. Export the sheet or individual tiles as PNG files.

## Safe background-removal workflow

The safest order is **Process → inspect → Activate**. Activating a candidate changes the source used for future extraction; existing bucket tiles are not silently replaced. Use **To Bucket** when you want to apply a candidate to existing tiles without making it the global active source.

## Projects

Use **Save Project** to keep tile snapshots and settings. The `.sscproj` format stores exact RGBA tile images in an archive; JSON projects store portable source paths and regenerate tiles from the source image.

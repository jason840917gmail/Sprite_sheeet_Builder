# Background Removal

## Engine choices

- **Exact Key** removes pixels close to one RGB color. Example: with a solid purple `#6E0BF5` backdrop, it removes purple pixels throughout the tile, even if a purple patch is inside the sprite.
- **Smart Solid** starts from the image border and removes connected background-like regions. Example: if the sprite itself contains purple details, it keeps those enclosed details while removing the purple region connected to the tile edge.
- **rembg** and **BEN2** are optional AI engines. Install them from **Tools > Optional AI Model Manager**; their runtimes and weights live in user data, not in the repository.

## Candidate revisions

Processing never overwrites the original source. A completed result is a candidate revision. Review it in the source viewer, then choose **Activate** or **To Bucket**.

- **Activate** changes the source used for new image tiles. Existing bucket tiles remain unchanged.
- **To Bucket** rebuilds the existing image tiles from the candidate in one undoable operation. It does not activate the candidate globally.
- **Discard** archives the candidate and returns the panel to the original-source state.

## New tile behavior

The **Settings** panel has a separate **Remove background** checkbox and **Tile remover** menu for image tiles added to the bucket. The default is **Exact Key**; choose **Smart Solid** for connected border background removal or **rembg — U2Net (single tile)** for one tile at a time. U2Net is not suitable for processing a complete multi-sprite sheet in one pass, so **Add All** and multi-tile selections are blocked while it is selected.

When the checkbox is active, the selected tile remover runs automatically as each new image tile is added. Changing this menu does not rewrite existing bucket tiles. The Source Background panel remains the separate full-source candidate workflow described above.

If a candidate still has small defects, switch to **Paint Cleanup** (`B`). Source Preview strokes update the same review candidate without touching the immutable original. Use **Erase**, **Paint Color**, or **Clone Color**; in Clone Color mode, Shift+left-click a pixel to sample its exact RGB, then click or drag to paint that color. Shift-click again to choose a new color. To repair only an extracted result, choose **Selected Bucket Tile** instead; each stroke is recorded as one undoable bucket change.

## GPU behavior

The app probes for NVIDIA CUDA support when an optional AI runtime is used. **Auto** chooses CUDA when the provider and device are usable, then falls back to CPU. Choose **CUDA only** when a CPU fallback would hide a configuration problem; choose **CPU only** for maximum compatibility.

## Export safety

All background-removal results remain RGBA. The exporter validates alpha output, preserves transparent pixels, and uses edge-safe scaling so sprites do not acquire dark or colored fringes in a game engine.

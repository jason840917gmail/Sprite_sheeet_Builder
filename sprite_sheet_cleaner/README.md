# Sprite Sheet Cleaner

Sprite Sheet Cleaner is a desktop tool for cleaning AI-generated sprite sheets. It lets artists and game developers manually select assets from messy source sheets, normalize them into fixed-size transparent tiles, collect them in a bucket, and export aligned PNG sprite sheets for engines like Godot.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r sprite_sheet_cleaner\requirements.txt
```

The core application supports Python 3.11 through 3.14. Optional background-removal runtimes and model weights are installed separately through the in-app Model Manager and are never stored in this repository.

## Optional AI background removal

The source-background panel processes the original image once and keeps the
candidate revision separate until you explicitly activate it. Tile extraction
then crops the active source; it does not run an AI model per tile.

Open **Tools > Optional AI Model Manager** to download a verified model and,
optionally, its isolated Python runtime:

- **rembg + U2Net**: approximately 176 MiB model download, 320x320 input.
- **BEN2 Base (ONNX)**: approximately 223 MB model download, fixed 1024x1024
  input and substantially higher inference memory use.

Models are stored under the platform user-data directory
(`%LOCALAPPDATA%/SpriteSheetCleaner` on Windows). They are checksum-verified,
never downloaded during inference, and never added to Git. The worker probes
ONNX Runtime, validates CUDA with a warm-up inference, and in Auto mode retries
with CPU when CUDA is unavailable, its DLLs fail to load, or the session runs
out of memory. The panel reports the backend actually used.

For sprite sheets, start with Smart Solid or Exact Key. Use rembg/BEN2 when the
background is not a reliable solid color, and review the candidate before
activation. AI runtimes require network access only for the explicit install;
installed models run offline.

## Run

From the workspace root:

```powershell
python -m sprite_sheet_cleaner.app.main
```

If your prompt is inside the nested `sprite_sheet_cleaner` package folder, go up one directory first:

```powershell
cd ..
.\.venv\Scripts\python.exe -m sprite_sheet_cleaner.app.main
```

You can also use the root launcher:

```powershell
.\.venv\Scripts\python.exe run_app.py
```

## Basic Workflow

1. Open a PNG, JPG, or WebP source sheet.
2. Set the tile / selection size, such as `256 x 256`. Enable `Sym` to link width and height together.
3. Set Selection grid to `1 x 1` for one tile at a time, or increase it to select a tile block such as `1 x 2`.
4. Use the Select tool to place that fixed-size selection box on the source image.
5. Use the Pointer tool to pan around the working canvas.
6. Add the selection to the bucket.
7. Adjust Final tilesheet rows and columns if the bucket needs more output slots.
8. Reorder, rename, duplicate, delete, or clear bucket tiles.
9. Preview the final sheet.
10. Export the sprite sheet PNG, or export individual tile PNGs.

The default workflow does not resize, trim, or pad selected tiles. A fixed `256 x 256` selection exports as a `256 x 256` tile. Background removal can still be enabled when the source sheet uses a solid color background.

The app auto-detects the background color when you open a source image. Use the `Detect` button beside Background color to re-sample the current selection border. If no selection exists, it samples the source image border. This is useful for AI sheets where the purple background is close to, but not exactly, `#FF00FF`.

## Recommended AI Sprite Settings

Use a solid high-contrast background when generating sheets. Bright magenta works well:

```text
RGB: 255, 0, 255
Hex: #FF00FF
```

## Godot Import Notes

For a Godot TileSet atlas source:

```text
Tile size: match the exported tile size
Separation: 0
Margins: 0
```

## Known Limitations

The tool does not automatically detect every tile. Complex backgrounds may not remove perfectly. Semi-transparent shadows may need manual adjustment. AI assets with inconsistent perspective may still need manual editing. Large images may use a lot of memory.

## Roadmap

MVP work focuses on manual crop, bucket, background removal, fixed tile canvas, final sheet preview, and PNG export. Later work can add richer project management, undo/redo, recent files, multiple buckets, Godot metadata, and installer packaging.

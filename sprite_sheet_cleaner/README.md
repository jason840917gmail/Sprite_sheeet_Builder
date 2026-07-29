# Sprite Sheet Cleaner

Sprite Sheet Cleaner is a desktop tool for cleaning AI-generated sprite sheets. It lets artists and game developers manually select assets from messy source sheets, normalize them into fixed-size transparent tiles, collect them in a bucket, and export aligned PNG sprite sheets for engines like Godot.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r sprite_sheet_cleaner\requirements.txt
```

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

1. Open a PNG, JPG, WebP, or supported video source.
2. For video, choose a frame range and sampling interval, extract candidate thumbnails, and select the frames to keep. Open more videos to create one tab per video; the bucket and output sheet are shared across tabs.
3. In the dedicated Video Tool panel, set the frame output size such as `64 x 64`, choose Fit, Stretch, or Fill/Crop, and configure background removal. These options are applied when frames enter the bucket.
4. Left-click a frame thumbnail to select and add it to the bucket; right-click it to deselect and remove it from the bucket.
5. Set `Seed animation frames` (10 by default) and use `Seed Animation` for a quick starting set of chronologically ordered random frames distributed across the video. Change the count when the action needs fewer or more poses.
6. Video mode uses full frames and does not use the image workflow's Tile/Selection size, Selection grid, or Grid tool.
7. Use the Pointer tool to pan around the working canvas.
8. Add selected frames to the bucket when needed; individual left-clicks already add immediately.
9. Drag bucket items to reorder them, or use the bucket controls to rename, duplicate, delete, or clear tiles.
10. Adjust final tilesheet rows and columns in the Video Tool panel if the bucket needs more output slots.
11. Preview the sheet inline or open the larger modal Animation Preview. In video mode it plays only the selected frames from the active video tab, preserving their bucket order.
12. Export the sprite sheet PNG, individual tile PNGs, or frame metadata JSON. Saved projects restore multi-video tabs, sampling controls, selected candidates, and video output settings.

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

The tool does not automatically detect every tile. Complex backgrounds may not remove perfectly. Semi-transparent shadows may need manual adjustment. AI assets with inconsistent perspective may still need manual editing. Large images and long videos may use a lot of memory. Video codec support depends on the OpenCV build installed on the machine.

## Roadmap

MVP work focuses on manual crop, bucket, background removal, fixed tile canvas, final sheet preview, and PNG export. Video frame extraction, frame selection, animation preview, and metadata export are now supported. Later work can add richer project management, undo/redo, recent files, multiple buckets, Godot metadata, and installer packaging.

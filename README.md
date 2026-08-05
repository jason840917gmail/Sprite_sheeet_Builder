# Sprite Sheet Cleaner

Sprite Sheet Cleaner is a desktop tool for cleaning messy AI-generated sprite sheets. It helps you place fixed-size tile selections over a source sheet, remove a solid background color when needed, collect cleaned tiles in a bucket, and export a final aligned sprite sheet PNG.

## Useful Commands

Run these from the workspace root:

```powershell
# Create the virtual environment
python -m venv .venv

# Activate it in PowerShell
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r sprite_sheet_cleaner\requirements.txt

# Run the desktop app
.\.venv\Scripts\python.exe run_app.py

# Alternative app entry point
.\.venv\Scripts\python.exe -m sprite_sheet_cleaner.app.main

# Run the automated tests
.\.venv\Scripts\python.exe -m unittest discover -s sprite_sheet_cleaner\tests

# Quick compile check
.\.venv\Scripts\python.exe -m compileall -q sprite_sheet_cleaner

# Build with PyInstaller
.\.venv\Scripts\python.exe sprite_sheet_cleaner\build.py
```

## Project Structure

- `run_app.py`: simple launcher from the workspace root.
- `sprite_sheet_cleaner/app/`: PySide6 desktop UI.
- `sprite_sheet_cleaner/app/core/`: image processing, sheet building, export logic.
- `sprite_sheet_cleaner/tests/`: automated tests.
- `Plan/BuildStatus.md`: current progress and pending work.

## Current Workflow

1. Open a source image or supported video.
2. For video, choose a frame range and sampling interval, extract thumbnails, and select the frames to keep. Open additional videos with `Open Video...`; each video gets its own tab while all tabs share one bucket and final tilesheet.
3. In the Video Tool panel, set the frame output size such as `64 x 64`, choose Fit, Stretch, or Fill/Crop, and configure background removal. These settings are applied as frames enter the bucket.
4. Left-click a frame thumbnail to select it and add it to the bucket; right-click it to deselect it and remove that video's frame from the bucket.
5. Set `Seed animation frames` (10 by default) and use `Seed Animation` for a quick starting set of chronologically ordered random frames distributed across the video. Change the count when the action needs fewer or more poses.
6. Video mode uses full frames; the image workflow's Tile/Selection size, Selection grid, and Grid tool do not control video imports.
7. Use the Pointer tool to pan around the video frame. `WASD` also pans the view.
8. Drag bucket items to reorder them, or use the bucket controls to rename, duplicate, delete, or clear tiles.
9. Adjust Final tilesheet rows and columns in the Video Tool panel if the bucket needs more output slots.
10. Preview the sheet inline or open the larger modal Animation Preview to inspect playback and timing. In video mode it plays only the selected frames from the active video tab, preserving their bucket order.
11. Optionally export frame metadata JSON for game-engine integration. Multi-video projects save and restore their tabs, sampling settings, selections, and frame sources.

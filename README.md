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

1. Open a source image.
2. Set the tile / selection size. Use `Sym` if you want width and height linked.
3. Set Selection grid to `1 x 1` for one tile at a time, or increase it to select a tile block such as `1 x 2`.
4. Use the Select tool to place the fixed-size selection box. In Select mode, left-click places the selection, arrow keys nudge it 1 pixel at a time, `Space` adds it to the bucket, and `Esc` clears it.
5. Use the Grid tool to divide the source image into equal cells. If the image size is uneven, Grid rounds down and leaves leftover right/bottom pixels outside the clickable grid.
6. In Grid mode, left-click individual cells to add them to the bucket, right-click and hold to drag the fitted grid within the image boundaries, or use the arrow keys to nudge the grid 1 pixel at a time.
7. Use the Pointer tool to pan around the canvas. `WASD` also pans the view in any tool. Switching to Pointer or Grid clears the current Select box.
8. The app auto-detects the background color when you open an image. Use `Detect` to re-sample from the current selection border when needed.
9. Add tiles to the bucket. You can rename, duplicate, reorder, delete, or clear the bucket from the bucket panel.
10. Adjust Final tilesheet rows and columns if the bucket needs more output slots.
11. Export the final sprite sheet.

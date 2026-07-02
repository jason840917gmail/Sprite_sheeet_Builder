
# Project Name

**Sprite Sheet Cleaner**

Alternative names:

```text
TileBucket
SpriteBucket
Atlas Cleaner
AI Tile Sheet Organizer
```

# Main idea

A desktop tool that helps clean messy AI-generated sprite sheets.

The user loads a messy sprite sheet, manually selects/crops assets from it, sends each crop into a “bucket,” and the app automatically places each bucket item into a clean, fixed-size tile canvas. Then the app assembles all bucket items into a perfectly aligned final sprite sheet.

The tool is not trying to magically detect every tile. The user does the smart manual selection. The tool does the repetitive work:

```text
crop → remove background → center → fit into tile canvas → assemble clean sheet → export PNG
```

# Final result

The user should be able to start with this:

```text
messy_ai_sheet.png
```

And export this:

```text
clean_terrain_sheet.png
```

Example final settings:

```text
Final tile size: 256x256
Final grid: 8 columns x 8 rows
Final sprite sheet size: 2048x2048
Tiles used: 64 / 64
Background: transparent
Output format: PNG
```

The exported sheet should be ready to import into Godot as a TileSet atlas.

# Recommended technology stack

Use:

```text
Python
PySide6
Pillow
OpenCV optional
PyInstaller
```

## Why this stack

**Python** is fast for prototyping and good for image processing.

**PySide6** is the GUI framework. It is the official Python binding for Qt, and QtWidgets provides standard desktop UI elements like windows, buttons, sliders, panels, and inputs. PySide6 also has `QImage`, which is useful for image display and pixel-level image handling in a desktop app. ([Qt Documentation][1])

**Pillow** should handle the core image operations: loading PNGs, cropping selected rectangles, working with RGBA transparency, resizing, padding, pasting tiles onto a final canvas, and exporting PNG. Pillow’s `Image` module supports crop/composite-style image workflows that fit this project well. ([Pillow (PIL Fork)][2])

**OpenCV** is optional for later versions. It can help with thresholding, color masks, and stronger background removal. OpenCV has image thresholding tools that can be useful when removing backgrounds based on color/tolerance. ([OpenCV Documentation][3])

**PyInstaller** can package the app into a `.exe` later.

# Core product concept

The app has 4 major areas:

```text
1. Source Viewer
2. Crop Controls
3. Bucket / Tile List
4. Final Sheet Preview
```

## 1. Source Viewer

This displays the messy AI sprite sheet.

Required features:

```text
Open image
Zoom in/out
Pan around image
Draw crop rectangle with mouse
Show crop rectangle dimensions live
Show cursor position
Optional grid overlay
Optional snap-to-size selection
```

Example display values:

```text
Mouse: X 487, Y 912
Selection: X 420, Y 880, W 253, H 248
Zoom: 150%
```

## 2. Crop Controls

This panel controls how the selected crop becomes a clean tile.

Required settings:

```text
Final tile width: 256
Final tile height: 256
Scale mode: none / scale down only / scale to fit
Padding: 8 px
Anchor: center / bottom-center
Remove background: on/off
Background color: color picker
Tolerance: 30
Trim transparent edges: on/off
```

Important: the source crop does **not** need to be exactly 256x256.

The source crop can be:

```text
243x251
188x160
302x280
```

But the final tile canvas will always be:

```text
256x256
```

That avoids deformation.

## 3. Bucket / Tile List

The bucket stores all extracted tiles before final export.

Each bucket item should have:

```text
thumbnail
name
source crop size
final tile size
index/order
delete button
duplicate button
move up/down buttons
```

Example bucket:

```text
001_grass_01    crop 250x250    final 256x256
002_dirt_01     crop 249x251    final 256x256
003_rock_01     crop 190x170    final 256x256
004_tree_01     crop 240x250    final 256x256
```

Later, you can add drag-and-drop reordering.

## 4. Final Sheet Preview

This shows the clean output sheet.

Required values:

```text
Final tile size: 256x256
Grid: 8x8
Output size: 2048x2048
Tiles used: 23 / 64
Empty slots: 41
```

The preview should update every time the user adds, removes, or reorders a bucket tile.

# MVP feature list

Build these first.

```text
Open messy sprite sheet PNG/JPG/WebP
Display source image
Zoom and pan
Draw crop rectangle
Add selected crop to bucket
Set final tile size
Set final grid columns/rows
Remove solid background color with tolerance
Trim transparent edges
Center tile in fixed canvas
Preview bucket thumbnails
Preview final sprite sheet
Export clean PNG sprite sheet
Export individual tiles optionally
```

This is enough to make the tool useful.

# Version 2 feature list

Add after the MVP works.

```text
Save/load project file
Undo/redo
Drag-and-drop bucket reordering
Rename bucket tiles
Batch export
Keyboard shortcuts
Snap crop rectangle to fixed size
Grid overlay on source image
Checkerboard transparency preview
Export Godot import notes
Export JSON metadata
Different tile sizes per bucket category
```

# Version 3 advanced features

Later, once the manual version is stable.

```text
Auto-detect solid background color
Auto-find connected object bounds
Magic wand selection
Object outline preview
Auto-suggest crop boxes
AI-assisted segmentation
Multiple buckets: terrain, trees, rocks, houses
Godot TileSet .tres generation
```

Do not start with Version 3. Build the manual workflow first.

# Main image-processing pipeline

When the user selects a crop and clicks **Add to Bucket**, the app should run this pipeline:

```text
1. Crop rectangle from source image
2. Convert crop to RGBA
3. Remove background color if enabled
4. Trim transparent borders if enabled
5. Scale image if needed
6. Create empty transparent tile canvas
7. Place crop into canvas using anchor rule
8. Save result as bucket item
9. Refresh bucket list
10. Refresh final sheet preview
```

## Background removal rule

For solid purple background, use RGB distance.

Example:

```text
background_color = (255, 0, 255)
tolerance = 30
```

For every pixel:

```text
distance = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
```

If distance is less than tolerance, set alpha to `0`.

Better formula:

```text
distance = sqrt((r-bg_r)^2 + (g-bg_g)^2 + (b-bg_b)^2)
```

If distance <= tolerance:

```text
alpha = 0
```

Else:

```text
keep pixel
```

## Trim transparent borders

After background removal, find the bounding box of all non-transparent pixels.

Then crop to that box.

This removes empty borders.

## Scaling rule

Use three modes:

### Mode 1: No scale

Do not resize the crop. If it is bigger than the final tile canvas, crop or warn the user.

### Mode 2: Scale down only

If the crop is larger than the tile canvas, scale it down. If it is smaller, keep original size.

This is the safest default.

### Mode 3: Scale to fit

Always resize the crop to fit inside the tile canvas.

This can deform visual consistency if used too much, so I would not make it the default.

Recommended default:

```text
Scale mode: scale down only
Anchor: center
Padding: 8 px
```

For trees and objects in top-down games, `bottom-center` anchor can be useful because the base of the object should sit near the bottom of the tile.

# Final sheet assembly logic

The final sheet is a blank transparent image.

Formula:

```text
sheet_width = tile_width * columns
sheet_height = tile_height * rows
```

For each bucket tile:

```text
row = index // columns
col = index % columns

x = col * tile_width
y = row * tile_height
```

Paste tile at:

```text
(x, y)
```

If the bucket has fewer items than the final grid capacity, leave the remaining slots transparent.

If the bucket has more items than capacity, warn the user.

# Recommended app layout

Use a main window like this:

```text
 ----------------------------------------------------------
| Menu: Open | Save Project | Export Sheet | Export Tiles   |
 ----------------------------------------------------------
|                      |                                   |
|  Source Viewer       |  Settings                         |
|  Messy Image         |  Tile Size: 256 x 256              |
|  Zoom/Pan/Crop       |  Grid: 8 x 8                       |
|                      |  Background Color: [picker]        |
|                      |  Tolerance: 30                     |
|                      |  [Add Selection to Bucket]         |
|----------------------|-----------------------------------|
|  Final Sheet Preview |  Bucket List                       |
|  Clean output sheet  |  thumbnails, names, reorder       |
 ----------------------------------------------------------
```

# Project folder structure

Use this structure:

```text
sprite_sheet_cleaner/
│
├── app/
│   ├── main.py
│   ├── main_window.py
│   ├── widgets/
│   │   ├── source_viewer.py
│   │   ├── final_preview.py
│   │   ├── bucket_panel.py
│   │   └── settings_panel.py
│   │
│   ├── core/
│   │   ├── image_processor.py
│   │   ├── sheet_builder.py
│   │   ├── project_model.py
│   │   └── export_manager.py
│   │
│   ├── models/
│   │   ├── tile_item.py
│   │   └── app_settings.py
│   │
│   └── utils/
│       ├── qimage_converter.py
│       └── file_utils.py
│
├── tests/
│   ├── test_image_processor.py
│   ├── test_sheet_builder.py
│   └── test_project_model.py
│
├── assets/
│   └── icons/
│
├── requirements.txt
├── README.md
└── build.py
```

# Suggested dependencies

`requirements.txt`:

```text
PySide6
Pillow
numpy
opencv-python
pytest
pyinstaller
```

For MVP, OpenCV can be optional. Pillow + NumPy is enough for background removal.

# Data models

## AppSettings

```python
@dataclass
class AppSettings:
    tile_width: int = 256
    tile_height: int = 256
    sheet_columns: int = 8
    sheet_rows: int = 8
    remove_background: bool = True
    background_color: tuple[int, int, int] = (255, 0, 255)
    tolerance: int = 30
    trim_transparent: bool = True
    scale_mode: str = "scale_down_only"
    padding: int = 8
    anchor: str = "center"
```

## TileItem

```python
@dataclass
class TileItem:
    name: str
    source_rect: tuple[int, int, int, int]
    source_size: tuple[int, int]
    final_size: tuple[int, int]
    image_rgba: Image.Image
```

## ProjectModel

```python
@dataclass
class ProjectModel:
    source_image_path: str | None
    settings: AppSettings
    tiles: list[TileItem]
```

# Core modules

## image_processor.py

Responsible for:

```text
crop image
remove background color
trim transparency
scale to fit
place into final tile canvas
```

Main function:

```python
def process_crop(
    source_image: Image.Image,
    crop_rect: tuple[int, int, int, int],
    settings: AppSettings
) -> Image.Image:
    ...
```

## sheet_builder.py

Responsible for:

```text
build final sheet from bucket items
calculate sheet dimensions
paste tiles in grid order
return final RGBA image
```

Main function:

```python
def build_sheet(
    tiles: list[TileItem],
    settings: AppSettings
) -> Image.Image:
    ...
```

## project_model.py

Responsible for:

```text
store app state
add tile
remove tile
move tile
rename tile
save/load project later
```

## export_manager.py

Responsible for:

```text
export final sheet PNG
export individual tiles
choose output folder
validate filenames
```

# Development phases

## Phase 1 — Core image engine

Goal: get image processing working without UI.

Build:

```text
load image
crop a rectangle
remove purple background
trim transparent pixels
center in 256x256 canvas
build 8x8 sheet
export PNG
```

Deliverable:

```text
A command-line script that can process hardcoded crop rectangles.
```

This proves the hard image logic works before building the interface.

## Phase 2 — Basic UI shell

Goal: create the desktop window.

Build:

```text
main window
menu bar
open image action
source image display
settings panel
empty bucket panel
empty final preview panel
```

Deliverable:

```text
User can open an image and see it in the app.
```

## Phase 3 — Crop selection

Goal: allow manual selection.

Build:

```text
click-drag rectangle selection
show selection overlay
show selection x/y/w/h
zoom
pan
reset zoom
```

Deliverable:

```text
User can draw a crop rectangle on the source image.
```

## Phase 4 — Add to bucket

Goal: make the crop workflow real.

Build:

```text
Add Selection to Bucket button
process crop using current settings
add tile thumbnail to bucket list
auto-name tile
delete tile
```

Deliverable:

```text
User can crop assets and collect them in the bucket.
```

## Phase 5 — Final sheet preview

Goal: show the clean output before export.

Build:

```text
generate preview after each bucket change
show final sheet dimensions
show tile count
show empty slot count
```

Deliverable:

```text
User sees the final clean sheet update live.
```

## Phase 6 — Export

Goal: create usable files.

Build:

```text
Export final sprite sheet PNG
Export individual tile PNGs
warn when bucket exceeds grid capacity
warn when no tiles exist
```

Deliverable:

```text
User can export clean Godot-ready PNG sheets.
```

## Phase 7 — Save/load project

Goal: make the tool practical for long sessions.

Build:

```text
save project JSON
reload project
store source image path
store settings
store crop rectangles
rebuild bucket items from source image
```

Important: avoid storing huge image data in the project JSON. Store crop rectangles and settings.

Deliverable:

```text
User can continue the same cleaning project later.
```

## Phase 8 — Polish

Goal: make it feel professional.

Build:

```text
keyboard shortcuts
checkerboard background
drag-and-drop reordering
rename tiles
better error messages
status bar
recent files
```

# Keyboard shortcuts

Use these:

```text
Ctrl+O       Open image
Ctrl+S       Save project
Ctrl+E       Export sheet
Delete       Remove selected bucket tile
A            Add selection to bucket
Ctrl+Z       Undo
Ctrl+Y       Redo
+            Zoom in
-            Zoom out
Space+Drag   Pan
```

# Export formats

## MVP

```text
PNG sprite sheet
PNG individual tiles
```

## Later

```text
JSON metadata
Godot notes file
Project JSON
```

Example metadata:

```json
{
  "tile_width": 256,
  "tile_height": 256,
  "columns": 8,
  "rows": 8,
  "sheet_width": 2048,
  "sheet_height": 2048,
  "tiles": [
    {
      "name": "grass_01",
      "index": 0,
      "x": 0,
      "y": 0,
      "width": 256,
      "height": 256
    }
  ]
}
```

# Godot import target

The final PNG should work with Godot like this:

```text
TileSet atlas source
Tile size: 256x256
Separation: 0
Margins: 0
```

For terrain, this works directly.

For trees, houses, rocks, and objects, you may want separate sheets:

```text
terrain_sheet.png
tree_sheet.png
rock_sheet.png
building_sheet.png
unit_sheet.png
```

Do not mix everything into one sheet at first. Terrain should be separate from tall objects.

# Important design decisions

## Do not force all source crops to 256x256

Let the user crop any size.

The final output tile canvas is fixed, but the source crop should be flexible.

This is very important for AI art.

## Use transparent padding, not stretching

Avoid deformation by default.

Recommended default:

```text
Scale mode: scale down only
Padding: 8
Anchor: center
```

## Allow bottom-center anchor

For trees, characters, rocks, and buildings, bottom-center is better than center because the object’s base stays aligned with the tile.

Example:

```text
Tree visual: 220x250
Tile canvas: 256x256
Anchor: bottom-center
```

## Use purple background for best results

For AI-generated sheets, use a strong background color when generating, like:

```text
RGB: 255, 0, 255
Hex: #FF00FF
```

That makes background removal much easier.

# MVP build order for Codex

Give Codex these tasks one at a time.

## Task 1

```text
Create a Python project named sprite_sheet_cleaner using PySide6 and Pillow. Add the folder structure with app/main.py, app/main_window.py, app/core/image_processor.py, app/core/sheet_builder.py, app/models/app_settings.py, and app/models/tile_item.py. Create a minimal PySide6 main window with a menu item to open an image file.
```

## Task 2

```text
Implement image loading and display in the main window. Add a SourceViewer widget that can display a large image, zoom in/out, pan, and show mouse coordinates over the image.
```

## Task 3

```text
Add rectangle crop selection to SourceViewer. The user should be able to click and drag on the image to create a selection rectangle. Show the rectangle overlay and display the selected x, y, width, and height in the UI.
```

## Task 4

```text
Create AppSettings and TileItem dataclasses. AppSettings should include tile_width, tile_height, sheet_columns, sheet_rows, background_color, tolerance, remove_background, trim_transparent, scale_mode, padding, and anchor.
```

## Task 5

```text
Implement image_processor.py with a process_crop function. It should crop the source image, convert it to RGBA, remove pixels matching the selected background color within tolerance by setting alpha to zero, trim transparent borders, optionally scale down to fit inside the final tile canvas, and paste the result into a transparent tile canvas.
```

## Task 6

```text
Create a settings panel in the UI with controls for final tile width, final tile height, sheet columns, sheet rows, background removal toggle, background color picker, tolerance slider, trim transparent toggle, scale mode dropdown, padding, and anchor dropdown.
```

## Task 7

```text
Add an Add Selection to Bucket button. When clicked, process the selected crop using current settings and add the result to a bucket list with thumbnail, name, crop size, and final tile size.
```

## Task 8

```text
Implement sheet_builder.py. It should create a transparent final sheet based on tile width, tile height, columns, and rows, then paste bucket tile images into the sheet in order.
```

## Task 9

```text
Add a FinalPreview widget that displays the generated sheet preview. It should update whenever a bucket item is added, removed, or reordered. Show final sheet dimensions, tiles used, total capacity, and empty slots.
```

## Task 10

```text
Add export actions. Export Sheet should save the generated final sheet as PNG. Export Individual Tiles should save each bucket item as a separate PNG file in a selected folder.
```

## Task 11

```text
Add bucket item management: delete tile, rename tile, duplicate tile, move tile up, and move tile down.
```

## Task 12

```text
Add project save/load as JSON. Store source image path, app settings, bucket tile names, and crop rectangles. When loading a project, reload the source image and regenerate bucket tiles from the stored crop rectangles and settings.
```

# Testing plan

Create automated tests for the image-processing core.

## Test 1: background removal

Input:

```text
small image with purple background and one non-purple object
```

Expected:

```text
purple pixels become alpha 0
object pixels remain visible
```

## Test 2: trim transparent borders

Input:

```text
256x256 image with a small object in the center
```

Expected:

```text
output crop bounds only contain the visible object
```

## Test 3: tile canvas output

Input:

```text
crop 180x140
final tile size 256x256
```

Expected:

```text
output image is exactly 256x256
```

## Test 4: sheet builder

Input:

```text
4 tile images
tile size 256x256
grid 2x2
```

Expected:

```text
final sheet is 512x512
all 4 tiles are pasted in correct positions
```

## Test 5: overflow warning

Input:

```text
65 tiles
grid 8x8
```

Expected:

```text
app warns user that capacity is 64
```

# Professional roadmap

## MVP

```text
Manual crop
Bucket
Background removal
Fixed tile canvas
Final sheet preview
PNG export
```

## Beta

```text
Save/load project
Reorder tiles
Rename tiles
Export individual tiles
Checkerboard background
Keyboard shortcuts
```

## Production

```text
Undo/redo
Recent files
Multiple buckets
Better auto-background tools
Godot metadata export
Installer
Documentation
Example assets
```

# README structure

Your `README.md` should include:

```text
What the tool does
Who it is for
Installation
How to run
Basic workflow
Recommended AI sprite generation settings
Godot import instructions
Known limitations
Roadmap
```

# Known limitations

Be honest about these from the beginning:

```text
The tool does not automatically detect every tile.
Complex backgrounds may not remove perfectly.
Semi-transparent shadows may need manual adjustment.
AI assets with inconsistent perspective may still need manual editing.
Large images may use a lot of memory.
```

# Best build strategy

Do not start with the full UI.

Start with this order:

```text
1. Build the image-processing functions.
2. Build the final sheet builder.
3. Build a small UI to load and crop.
4. Add the bucket.
5. Add preview/export.
6. Polish.
```

That keeps the project under control.

# Final recommendation

Build it as a **manual-assisted sprite sheet cleaner**, not an automatic detector.

The professional description would be:

```text
Sprite Sheet Cleaner is a desktop tool for cleaning AI-generated sprite sheets. It allows artists and game developers to manually select assets from messy source sheets, normalize them into fixed-size transparent tiles, organize them in a bucket, and export perfectly aligned sprite sheets ready for game engines like Godot.
```

That is a strong, realistic MVP, and it is absolutely buildable with Codex.

[1]: https://doc.qt.io/qtforpython-6/index.html?utm_source=chatgpt.com "Qt for Python"
[2]: https://pillow.readthedocs.io/en/stable/reference/Image.html?utm_source=chatgpt.com "Image module - Pillow (PIL Fork) 12.2.0 documentation"
[3]: https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html?utm_source=chatgpt.com "Image Thresholding"

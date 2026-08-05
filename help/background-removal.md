# Background Removal

## Engine choices

- **Exact Key** removes pixels close to one RGB color. Use it for clean studio or game-art backgrounds.
- **Smart Solid** starts from the image border and removes connected background-like regions. It is safer when the same color appears inside the sprite.
- **rembg** and **BEN2** are optional AI engines. Install them from **Tools > Optional AI Model Manager**; their runtimes and weights live in user data, not in the repository.

## Candidate revisions

Processing never overwrites the original source. A completed result is a candidate revision. Review it in the source viewer, then choose **Activate** or **To Bucket**.

- **Activate** changes the source used for new image tiles. Existing bucket tiles remain unchanged.
- **To Bucket** rebuilds the existing image tiles from the candidate in one undoable operation. It does not activate the candidate globally.
- **Discard** archives the candidate and returns the panel to the original-source state.

## GPU behavior

The app probes for NVIDIA CUDA support when an optional AI runtime is used. **Auto** chooses CUDA when the provider and device are usable, then falls back to CPU. Choose **CUDA only** when a CPU fallback would hide a configuration problem; choose **CPU only** for maximum compatibility.

## Export safety

All background-removal results remain RGBA. The exporter validates alpha output, preserves transparent pixels, and uses edge-safe scaling so sprites do not acquire dark or colored fringes in a game engine.

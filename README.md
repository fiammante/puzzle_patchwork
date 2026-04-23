# puzzle_patchwork

Assemble a **jigsaw-style photo mosaic** from a folder of images.  
Every tile is shaped like a real puzzle piece using cubic-Bézier geometry,
images are never repeated, original colour-space is preserved, and
all piece boundaries render as clean single-pixel cut lines with zero mismatch.

---

## Example output

| `--cols 5 --rows 8 --tile 450` |
|:---:|
| ![example](example.jpg) |

---

## Requirements

```
Python ≥ 3.10
Pillow
numpy
```

```bash
pip install Pillow numpy
```

---

## Usage

```bash
python puzzle_patchwork.py -i FOLDER -o OUTPUT [options]
```

### Arguments

| Argument | Short | Default | Description |
|---|---|---|---|
| `--input` | `-i` | *(required)* | Folder containing source images (scanned recursively) |
| `--output` | `-o` | `patchwork.jpg` | Output file (`.jpg` or `.png`) |
| `--cols` | | `6` | Number of columns |
| `--rows` | | `5` | Number of rows |
| `--tile` | | `180` | Tile size in pixels (square) |
| `--gray-ratio` | | `0.0` | Fraction of tiles to desaturate, 0–1 |
| `--seed` | | *random* | Integer seed for reproducibility |
| `--bg` | | `121212` | Background hex colour |

### Examples

```bash
# Basic — 5×8 grid, 450 px tiles
python puzzle_patchwork.py -i ./photos -o patchwork.jpg --cols 5 --rows 8 --tile 450

# Reproducible, 30 % grayscale tiles mixed in
python puzzle_patchwork.py -i ./photos -o patchwork.png \
    --cols 6 --rows 5 --tile 300 --gray-ratio 0.30 --seed 42

# Warm dark background
python puzzle_patchwork.py -i ./photos -o warm.jpg \
    --cols 4 --rows 4 --tile 400 --bg 1a0808 --seed 7
```

---

## How it works

### Piece geometry

Each edge is built from **8 cubic-Bézier segments** that reproduce the
classic jigsaw tab silhouette — shoulder S-curves, a narrow neck, and
an elliptical head:

```
         ╭──────╮
        /        \       ← elliptical head
────────┘          └──────   ← S-curve shoulders + neck pinch
```

Per-edge parameters (tab centre offset, neck width, head radius, lean)
are randomised from a **shared seed** so the tab of tile A and the
blank of tile B are always the exact same curve.

### Rendering pipeline

| Pass | Operation | Purpose |
|---|---|---|
| **1** | Full rectangles for every tile | Every pixel filled — blanks reveal the neighbour's image |
| **2** | Shaped piece composited (alpha mask) | Clips to puzzle outline; tabs protrude into neighbour zone |
| **3** | Single-pixel cut lines | Derived from tile-ownership map; guaranteed no doubles or gaps |

### Pixel-perfect cut lines

A `tmap` integer array records which tile owns each canvas pixel.
Masks are stamped without dilation; any unclaimed pixels are assigned
from the rectangular grid fallback.  The boundary is then:

```python
h_boundary = tmap[y, x] != tmap[y+1, x]
v_boundary = tmap[y, x] != tmap[y, x+1]
```

Pure integer comparison — no floating-point geometry, no misalignment possible.

### Zero-halo guarantee

`tiles_rect` (the rectangle used in pass 1) is derived by centre-cropping
`tiles_pad` (the larger padded image used in pass 2), not by re-scaling the
source independently.  Both passes use **identical pixels** at the shared
boundary, so there is no colour fringe around tabs.

---

## Notes

- **No repeated images.** If the grid needs more tiles than available images
  the grid is automatically reduced to the largest `cols × rows` that fits,
  with a warning printed.
- **EXIF orientation** is respected (`ImageOps.exif_transpose`), so portrait
  photos taken on phones appear correctly.
- **Supported input formats:** JPEG, PNG, BMP, TIFF, WebP.
- Output is a single flat RGB image saved at JPEG quality 95 or lossless PNG.

---

## License

MIT

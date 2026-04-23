#!/usr/bin/env python3
"""
resize_photos.py
────────────────
Resize all images in a folder so each file is < 500 KB,
preserve EXIF orientation, then rename them 1.jpg, 2.jpg, …

Usage:
    python resize_photos.py -i FOLDER [-o OUTPUT_FOLDER] [--max-kb 500]

If --output is omitted the files are processed IN-PLACE (originals overwritten).

Dependencies:  pip install Pillow
"""

import argparse, shutil, sys
from pathlib import Path
from PIL import Image, ImageOps

EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MAX_KB = 500


def file_kb(path: Path) -> float:
    return path.stat().st_size / 1024


def resize_to_target(img: Image.Image, target_kb: int, save_path: Path,
                     quality_start: int = 92) -> None:
    """
    Save img as JPEG under target_kb by progressively lowering quality,
    then halving dimensions if quality alone isn't enough.
    """
    w, h = img.size

    while True:
        for quality in range(quality_start, 19, -4):
            img.save(save_path, format="JPEG",
                     quality=quality, optimize=True)
            if file_kb(save_path) < target_kb:
                return

        # Quality alone not enough → halve dimensions and retry
        w, h = max(w // 2, 1), max(h // 2, 1)
        img = img.resize((w, h), Image.LANCZOS)
        quality_start = 92

        if w == 1 and h == 1:
            break   # can't shrink further (extremely unlikely)


def process(input_folder: str, output_folder: str | None,
            max_kb: int) -> None:

    src = Path(input_folder).resolve()
    if not src.is_dir():
        sys.exit(f"[ERROR] Not a directory: {src}")

    # Collect supported images, sorted alphabetically for deterministic order
    images = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
    if not images:
        sys.exit(f"[ERROR] No supported images found in {src}")

    # Destination folder
    if output_folder:
        dst = Path(output_folder).resolve()
        dst.mkdir(parents=True, exist_ok=True)
    else:
        dst = src  # in-place

    print(f"Found {len(images)} image(s) in {src}")
    print(f"Output → {dst}   |   Target < {max_kb} KB\n")

    for idx, src_path in enumerate(images, start=1):
        out_path = dst / f"{idx}.jpg"

        # Load and fix orientation
        img = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")

        already_small = (src_path.suffix.lower() in {".jpg", ".jpeg"}
                         and file_kb(src_path) < max_kb
                         and dst == src)

        if already_small and out_path == src_path:
            # Nothing to do except rename (handled below)
            pass
        else:
            resize_to_target(img, max_kb, out_path)

        final_kb = file_kb(out_path)
        print(f"  [{idx:>4}]  {src_path.name:<40}  →  {out_path.name}  "
              f"({final_kb:.1f} KB)")

    # In-place mode: remove original files that were not overwritten
    # (e.g. originals with non-JPEG names that became N.jpg)
    if dst == src:
        new_names = {src / f"{i}.jpg" for i in range(1, len(images) + 1)}
        for src_path in images:
            if src_path not in new_names and src_path.exists():
                src_path.unlink()

    print(f"\n[OK] {len(images)} file(s) saved to {dst}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Resize photos to <N KB and rename to 1.jpg, 2.jpg, …")
    ap.add_argument("--input",  "-i", required=True,
                    help="Source folder")
    ap.add_argument("--output", "-o", default=None,
                    help="Destination folder (default: in-place)")
    ap.add_argument("--max-kb", type=int, default=MAX_KB,
                    help=f"Maximum file size in KB (default {MAX_KB})")
    a = ap.parse_args()
    process(a.input, a.output, a.max_kb)


if __name__ == "__main__":
    main()

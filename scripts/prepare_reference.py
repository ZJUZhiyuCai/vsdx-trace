#!/usr/bin/env python3
"""Prepare a reference image for pixel-accurate Visio reconstruction.

Outputs:
- reference.png: normalized RGB copy
- reference_grid.png: coordinate grid overlay in source pixels
- reference_edges.png: high-contrast edge guide
- reference_info.json: dimensions, aspect ratio, recommended page size and PPI

The script does not use OCR. It is intended for geometric measurement and QA.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _nice_step(length: int, target_lines: int = 10) -> int:
    raw = max(1.0, length / max(1, target_lines))
    magnitude = 10 ** math.floor(math.log10(raw))
    normalized = raw / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return max(1, int(nice * magnitude))


def _edges(image: Image.Image) -> Image.Image:
    gray = np.asarray(ImageOps.grayscale(image), dtype=np.float32)
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) / 2.0
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) / 2.0
    magnitude = np.sqrt(gx * gx + gy * gy)
    threshold = max(10.0, float(np.percentile(magnitude, 82)))
    edge = np.where(magnitude >= threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(edge, mode="L").convert("RGB")


def prepare(source: Path, output_dir: Path, ppi: float, grid_step: int | None) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Reference image not found: {source}")
    if ppi <= 0:
        raise ValueError("PPI must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = image.size

    normalized_path = output_dir / "reference.png"
    image.save(normalized_path, optimize=True)

    step = int(grid_step or min(_nice_step(width), _nice_step(height)))
    step = max(25, step)
    grid = image.copy()
    draw = ImageDraw.Draw(grid, "RGBA")
    label_font = ImageFont.load_default()
    major_every = 5

    for index, x in enumerate(range(0, width + 1, step)):
        major = index % major_every == 0
        alpha = 155 if major else 80
        line_width = 2 if major else 1
        draw.line([(x, 0), (x, height)], fill=(0, 90, 200, alpha), width=line_width)
        if x < width:
            label = str(x)
            draw.rectangle((x + 2, 2, x + 5 + 7 * len(label), 17), fill=(255, 255, 255, 190))
            draw.text((x + 4, 4), label, fill=(0, 55, 130, 255), font=label_font)

    for index, y in enumerate(range(0, height + 1, step)):
        major = index % major_every == 0
        alpha = 155 if major else 80
        line_width = 2 if major else 1
        draw.line([(0, y), (width, y)], fill=(210, 30, 30, alpha), width=line_width)
        if y < height:
            label = str(y)
            draw.rectangle((2, y + 2, 5 + 7 * len(label), y + 17), fill=(255, 255, 255, 190))
            draw.text((4, y + 4), label, fill=(150, 0, 0, 255), font=label_font)

    grid_path = output_dir / "reference_grid.png"
    grid.save(grid_path, optimize=True)

    edge_path = output_dir / "reference_edges.png"
    _edges(image).save(edge_path, optimize=True)

    info = {
        "source": str(source),
        "normalized_reference": str(normalized_path),
        "width_px": width,
        "height_px": height,
        "aspect_ratio": round(width / height, 8),
        "recommended_ppi": ppi,
        "visio_page_width_in": round(width / ppi, 8),
        "visio_page_height_in": round(height / ppi, 8),
        "grid_step_px": step,
        "coordinate_system": "top-left origin; x right; y down",
        "visio_transform": {
            "PinX": "(x + w/2) / PPI",
            "PinY": "(height_px - y - h/2) / PPI",
            "Width": "w / PPI",
            "Height": "h / PPI"
        },
        "artifacts": {
            "grid": str(grid_path),
            "edges": str(edge_path)
        }
    }
    info_path = output_dir / "reference_info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**info, "info": str(info_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ppi", type=float, default=100.0)
    parser.add_argument("--grid-step", type=int, default=None)
    args = parser.parse_args()
    try:
        report = prepare(
            args.reference.expanduser().resolve(),
            args.output_dir.expanduser().resolve(),
            args.ppi,
            args.grid_step,
        )
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Extract named raster regions from a reference image.

Regions JSON may be either a list or {"regions": [...]}.
Each region accepts:
  {"name":"history-clip-1", "crop":[x,y,w,h], "format":"png"}
or:
  {"name":"history-clip-1", "crop_box":[left,top,right,bottom]}

This helper is optional because vsdx_builder.py can crop directly from the
reference image. Use it when inspecting, retouching, or reusing many crops.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "region"


def extract(reference: Path, regions_path: Path, output_dir: Path) -> dict[str, Any]:
    if not reference.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference}")
    raw = json.loads(regions_path.read_text(encoding="utf-8"))
    regions = raw.get("regions", []) if isinstance(raw, dict) else raw
    if not isinstance(regions, list):
        raise ValueError("Regions JSON must be a list or contain a 'regions' list")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []

    with Image.open(reference) as opened:
        image = opened.convert("RGBA")
        for index, region in enumerate(regions, start=1):
            if not isinstance(region, dict):
                raise ValueError(f"Region {index} is not an object")
            name = _safe_name(str(region.get("name") or f"region-{index}"))
            if "crop" in region:
                x, y, w, h = map(float, region["crop"])
                box = (round(x), round(y), round(x + w), round(y + h))
            elif "crop_box" in region:
                box = tuple(round(float(v)) for v in region["crop_box"])
            else:
                raise ValueError(f"Region '{name}' needs crop or crop_box")
            if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError(f"Region '{name}' has an invalid crop box: {box}")
            fragment = image.crop(box)
            fmt = str(region.get("format") or "png").lower()
            if fmt not in {"png", "jpg", "jpeg", "webp"}:
                raise ValueError(f"Region '{name}' has unsupported format '{fmt}'")
            extension = "jpg" if fmt == "jpeg" else fmt
            output = output_dir / f"{index:03d}-{name}.{extension}"
            save_format = "JPEG" if fmt in {"jpg", "jpeg"} else fmt.upper()
            if save_format == "JPEG":
                fragment.convert("RGB").save(output, quality=95, optimize=True)
            else:
                fragment.save(output, format=save_format, optimize=True)
            outputs.append({
                "name": name,
                "output": str(output),
                "crop_box": list(box),
                "size_px": list(fragment.size),
            })

    manifest = {
        "reference": str(reference),
        "regions_source": str(regions_path),
        "count": len(outputs),
        "regions": outputs,
    }
    manifest_path = output_dir / "regions_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**manifest, "manifest": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("regions", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = extract(
            args.reference.expanduser().resolve(),
            args.regions.expanduser().resolve(),
            args.output_dir.expanduser().resolve(),
        )
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

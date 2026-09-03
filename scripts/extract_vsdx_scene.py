#!/usr/bin/env python3
"""Extract a readable shape inventory from an existing VSDX.

This is intended for studying gold-standard examples and debugging. It is not a
lossless VSDX-to-scene converter.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

V = "{http://schemas.microsoft.com/office/visio/2012/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def cell_map(shape: ET.Element) -> dict[str, str]:
    return {c.attrib.get("N", ""): c.attrib.get("V", "") for c in shape.findall(V + "Cell")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory VSDX shapes")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ppi", type=float, default=100.0)
    args = parser.parse_args()
    with zipfile.ZipFile(args.input) as zf:
        pages = ET.fromstring(zf.read("visio/pages/pages.xml"))
        page_rels = ET.fromstring(zf.read("visio/pages/_rels/pages.xml.rels"))
        rel_targets = {r.attrib.get("Id"): r.attrib.get("Target") for r in page_rels.findall(PR + "Relationship")}
        out: dict[str, Any] = {"source": str(args.input), "ppi": args.ppi, "pages": []}
        for page_node in pages.findall(V + "Page"):
            rel_node = page_node.find(V + "Rel")
            rid = rel_node.attrib.get(R + "id") if rel_node is not None else None
            target = rel_targets.get(rid or "")
            if not target:
                continue
            page_name = page_node.attrib.get("Name") or page_node.attrib.get("NameU") or target
            sheet = page_node.find(V + "PageSheet")
            sheet_cells = {c.attrib.get("N"): c.attrib.get("V") for c in sheet.findall(V + "Cell")} if sheet is not None else {}
            width_in = float(sheet_cells.get("PageWidth") or 0)
            height_in = float(sheet_cells.get("PageHeight") or 0)
            page_xml_name = "visio/pages/" + target
            root = ET.fromstring(zf.read(page_xml_name))
            image_targets: dict[str, str] = {}
            rel_name = f"visio/pages/_rels/{Path(target).name}.rels"
            if rel_name in zf.namelist():
                rel_root = ET.fromstring(zf.read(rel_name))
                image_targets = {r.attrib.get("Id", ""): r.attrib.get("Target", "") for r in rel_root.findall(PR + "Relationship")}
            page_out = {
                "name": page_name,
                "width_px": round(width_in * args.ppi, 3),
                "height_px": round(height_in * args.ppi, 3),
                "part": page_xml_name,
                "shapes": [],
            }
            for shape in root.findall(".//" + V + "Shape"):
                c = cell_map(shape)
                pin_x = float(c.get("PinX") or 0)
                pin_y = float(c.get("PinY") or 0)
                w = float(c.get("Width") or 0)
                h = float(c.get("Height") or 0)
                x_px = (pin_x - w / 2.0) * args.ppi
                y_px = (height_in - (pin_y + h / 2.0)) * args.ppi
                text_node = shape.find(V + "Text")
                text = "".join(text_node.itertext()) if text_node is not None else None
                item: dict[str, Any] = {
                    "id": shape.attrib.get("ID"),
                    "name": shape.attrib.get("Name") or shape.attrib.get("NameU"),
                    "type": shape.attrib.get("Type"),
                    "x": round(x_px, 3),
                    "y": round(y_px, 3),
                    "w": round(w * args.ppi, 3),
                    "h": round(h * args.ppi, 3),
                    "fill": c.get("FillForegnd"),
                    "fill_pattern": c.get("FillPattern"),
                    "line": c.get("LineColor"),
                    "line_pattern": c.get("LinePattern"),
                    "line_weight_in": c.get("LineWeight"),
                    "text": text,
                }
                foreign = shape.find(V + "ForeignData")
                if foreign is not None:
                    rel = foreign.find(V + "Rel")
                    image_rid = rel.attrib.get(R + "id") if rel is not None else None
                    item["image_relationship"] = image_rid
                    item["image_target"] = image_targets.get(image_rid or "")
                geom = shape.find(V + "Section[@N='Geometry']")
                if geom is not None:
                    pts = []
                    for row in geom.findall(V + "Row"):
                        rc = {cc.attrib.get("N"): cc.attrib.get("V") for cc in row.findall(V + "Cell")}
                        if "X" in rc and "Y" in rc:
                            pts.append({"row": row.attrib.get("T"), "x_in": rc["X"], "y_in": rc["Y"]})
                    if pts:
                        item["geometry"] = pts
                page_out["shapes"].append(item)
            out["pages"].append(page_out)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "pages": len(out["pages"]), "shapes": sum(len(p["shapes"]) for p in out["pages"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

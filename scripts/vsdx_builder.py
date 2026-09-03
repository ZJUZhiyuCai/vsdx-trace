#!/usr/bin/env python3
"""Build editable Microsoft Visio VSDX files from a JSON scene description.

The scene uses pixel coordinates with a top-left origin. The writer converts
those coordinates to Visio's inch-based, bottom-left coordinate system.

Only the Python standard library is required for vector-only scenes. Pillow is
required for bitmap/image shapes and reference-image pages.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape as xml_escape
from pathlib import Path
from typing import Any, Sequence

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None  # type: ignore

VISIO_NS = "http://schemas.microsoft.com/office/visio/2012/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def _f(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"


def _esc(value: Any) -> str:
    return xml_escape(str(value), quote=True)


def _normalize_color(value: Any, default: str = "#000000") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return "#%02X%02X%02X" % tuple(int(max(0, min(255, x))) for x in value[:3])
    text = str(value).strip()
    if not text:
        return default
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return "#" + text.upper()
    named = {
        "black": "#000000",
        "white": "#FFFFFF",
        "transparent": "#FFFFFF",
        "red": "#FF0000",
        "green": "#008000",
        "blue": "#0000FF",
        "gray": "#808080",
        "grey": "#808080",
    }
    return named.get(text.lower(), default)


def _rgb_formula(color: str) -> str:
    color = _normalize_color(color)
    return f"RGB({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)})"


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _cell(name: str, value: Any, unit: str | None = None, formula: str | None = None) -> str:
    attrs = [f'N="{_esc(name)}"', f'V="{_esc(value)}"']
    if unit:
        attrs.append(f'U="{_esc(unit)}"')
    if formula:
        attrs.append(f'F="{_esc(formula)}"')
    return "<Cell " + " ".join(attrs) + "/>"


def _geometry_section(points: Sequence[tuple[float, float]], *, closed: bool, no_fill: bool, no_line: bool, ix: int = 0) -> str:
    if not points:
        points = [(0.0, 0.0), (0.01, 0.01)]
    rows: list[str] = []
    for i, (x, y) in enumerate(points, start=1):
        row_type = "MoveTo" if i == 1 else "LineTo"
        rows.append(
            f'<Row T="{row_type}" IX="{i}">{_cell("X", _f(x))}{_cell("Y", _f(y))}</Row>'
        )
    if closed and points[-1] != points[0]:
        i = len(rows) + 1
        x, y = points[0]
        rows.append(f'<Row T="LineTo" IX="{i}">{_cell("X", _f(x))}{_cell("Y", _f(y))}</Row>')
    return (
        f'<Section N="Geometry" IX="{ix}">'
        f'{_cell("NoFill", 1 if no_fill else 0)}'
        f'{_cell("NoLine", 1 if no_line else 0)}'
        f'{_cell("NoShow", 0)}'
        + "".join(rows)
        + "</Section>"
    )


def _rect_points(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, h), (w, h), (w, 0.0), (0.0, 0.0)]


def _rounded_rect_points(w: float, h: float, radius: float, segments: int = 6) -> list[tuple[float, float]]:
    r = max(0.0, min(radius, w / 2.0, h / 2.0))
    if r <= 1e-9:
        return _rect_points(w, h)
    # Build in local top-left coordinates, then invert Y into Visio local space.
    pts_top: list[tuple[float, float]] = []
    pts_top.append((r, 0.0))
    pts_top.append((w - r, 0.0))
    corners = [
        ((w - r, r), -math.pi / 2, 0.0),
        ((w - r, h - r), 0.0, math.pi / 2),
        ((r, h - r), math.pi / 2, math.pi),
        ((r, r), math.pi, 3 * math.pi / 2),
    ]
    for (cx, cy), a0, a1 in corners:
        for i in range(1, segments + 1):
            a = a0 + (a1 - a0) * i / segments
            pts_top.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return [(x, h - y) for x, y in pts_top]


def _ellipse_points(w: float, h: float, segments: int = 48) -> list[tuple[float, float]]:
    rx, ry = w / 2.0, h / 2.0
    cx, cy = rx, ry
    return [(cx + rx * math.cos(2 * math.pi * i / segments), cy + ry * math.sin(2 * math.pi * i / segments)) for i in range(segments)]


def _shape_bounds_from_points(points: Sequence[Sequence[float]], minimum_px: float = 1.0) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x - min_x < minimum_px:
        pad = (minimum_px - (max_x - min_x)) / 2.0
        min_x -= pad
        max_x += pad
    if max_y - min_y < minimum_px:
        pad = (minimum_px - (max_y - min_y)) / 2.0
        min_y -= pad
        max_y += pad
    return min_x, min_y, max_x - min_x, max_y - min_y


def _visio_local_points(points_px: Sequence[Sequence[float]], x_px: float, y_px: float, h_px: float, ppi: float) -> list[tuple[float, float]]:
    return [((float(px) - x_px) / ppi, (y_px + h_px - float(py)) / ppi) for px, py in points_px]


def _font_style_mask(text_style: dict[str, Any]) -> int:
    mask = 0
    if _bool(text_style.get("bold")):
        mask |= 1
    if _bool(text_style.get("italic")):
        mask |= 2
    if _bool(text_style.get("underline")):
        mask |= 4
    return mask


def _horizontal_align(value: Any) -> int:
    text = str(value or "center").lower()
    return {"left": 0, "center": 1, "centre": 1, "right": 2}.get(text, 1)


def _vertical_align(value: Any) -> int:
    text = str(value or "middle").lower()
    return {"top": 0, "middle": 1, "center": 1, "centre": 1, "bottom": 2}.get(text, 1)


def _line_pattern(shape: dict[str, Any]) -> int:
    if _bool(shape.get("no_line")) or str(shape.get("line", "")).lower() == "none":
        return 0
    dash = shape.get("dash")
    if dash in (None, False, 0, "", "solid"):
        return 1
    # bool is a subclass of int in Python; handle True before numeric patterns.
    if dash is True:
        return 2
    if isinstance(dash, (int, float)) and int(dash) >= 1:
        return int(dash)
    return 2


def _fill_pattern(shape: dict[str, Any]) -> int:
    fill = shape.get("fill")
    if _bool(shape.get("no_fill")) or fill is None or str(fill).lower() in {"none", "transparent"}:
        return 0
    return 1


@dataclass
class MediaItem:
    rel_id: str
    filename: str
    data: bytes
    content_type: str = "image/png"


@dataclass
class PageBuild:
    name: str
    width_px: float
    height_px: float
    ppi: float
    xml_shapes: list[str] = field(default_factory=list)
    media: list[MediaItem] = field(default_factory=list)
    next_shape_id: int = 1

    @property
    def width_in(self) -> float:
        return self.width_px / self.ppi

    @property
    def height_in(self) -> float:
        return self.height_px / self.ppi

    def add_xml_shape(self, xml: str) -> int:
        shape_id = self.next_shape_id
        self.next_shape_id += 1
        self.xml_shapes.append(xml.replace("__SHAPE_ID__", str(shape_id), 1))
        return shape_id

    def add_media(self, data: bytes, page_index: int) -> MediaItem:
        rel_id = f"rId{len(self.media) + 1}"
        filename = f"p{page_index}_image_{len(self.media) + 1}.png"
        item = MediaItem(rel_id=rel_id, filename=filename, data=data)
        self.media.append(item)
        return item


class VsdxSceneBuilder:
    def __init__(self, scene: dict[str, Any], scene_path: Path | None = None):
        self.scene = scene
        self.scene_path = scene_path
        self.base_dir = scene_path.parent if scene_path else Path.cwd()
        document = scene.get("document", {})
        self.title = str(document.get("title") or scene.get("title") or "Editable Visio Reconstruction")
        self.author = str(document.get("author") or "OpenAI")
        created_raw = document.get("created_utc")
        source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if created_raw:
            self.created_utc = str(created_raw)
        elif source_date_epoch:
            try:
                self.created_utc = datetime.fromtimestamp(int(source_date_epoch), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OverflowError):
                raise ValueError("SOURCE_DATE_EPOCH must be an integer Unix timestamp")
        else:
            self.created_utc = None
        self.deterministic_zip_timestamps = _bool(document.get("deterministic_zip_timestamps") or document.get("deterministic"), False)
        self.default_ppi = float(document.get("ppi") or scene.get("ppi") or 100.0)
        if self.default_ppi <= 0:
            raise ValueError("ppi must be positive")
        self.font_names: list[str] = []
        self._font_index: dict[str, int] = {}
        self.pages: list[PageBuild] = []
        self.warnings: list[str] = []

    def _resolve_path(self, raw: str | os.PathLike[str]) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = (self.base_dir / path).resolve()
        return path

    def _font_id(self, name: str | None) -> int:
        font_name = (name or "Arial").strip() or "Arial"
        key = font_name.casefold()
        if key in self._font_index:
            return self._font_index[key]
        idx = len(self.font_names)
        self.font_names.append(font_name)
        self._font_index[key] = idx
        return idx

    def _page_from_dict(self, page_dict: dict[str, Any]) -> PageBuild:
        canvas = self.scene.get("canvas", {})
        width_px = float(page_dict.get("width_px") or canvas.get("width_px") or self.scene.get("width_px") or 1600)
        height_px = float(page_dict.get("height_px") or canvas.get("height_px") or self.scene.get("height_px") or 900)
        ppi = float(page_dict.get("ppi") or self.default_ppi)
        page = PageBuild(
            name=str(page_dict.get("name") or f"Page-{len(self.pages)+1}"),
            width_px=width_px,
            height_px=height_px,
            ppi=ppi,
        )
        background = page_dict.get("background", canvas.get("background"))
        if background:
            self._emit_basic_shape(
                page,
                {
                    "type": "rect",
                    "name": "Page background",
                    "x": 0,
                    "y": 0,
                    "w": width_px,
                    "h": height_px,
                    "fill": background,
                    "line": "none",
                },
                page_index=len(self.pages) + 1,
            )
        return page

    def build(self) -> list[PageBuild]:
        pages_data = self.scene.get("pages")
        if not pages_data:
            pages_data = [{
                "name": "Editable Reconstruction",
                "width_px": self.scene.get("width_px") or self.scene.get("canvas", {}).get("width_px"),
                "height_px": self.scene.get("height_px") or self.scene.get("canvas", {}).get("height_px"),
                "background": self.scene.get("background") or self.scene.get("canvas", {}).get("background"),
                "shapes": self.scene.get("shapes", []),
            }]
        for page_data in pages_data:
            page = self._page_from_dict(page_data)
            self.pages.append(page)
            page_index = len(self.pages)
            for shape in page_data.get("shapes", []):
                self._emit_shape(page, dict(shape), page_index)

        reference_image = self.scene.get("reference_image") or self.scene.get("document", {}).get("reference_image")
        include_reference = _bool(self.scene.get("include_reference_page"), default=bool(reference_image))
        if reference_image and include_reference:
            ref_path = self._resolve_path(str(reference_image))
            if not ref_path.exists():
                raise FileNotFoundError(f"reference image not found: {ref_path}")
            if Image is None:
                raise RuntimeError("Pillow is required to add the reference-image page")
            with Image.open(ref_path) as im:
                width_px, height_px = im.size
            page = PageBuild(
                name=str(self.scene.get("reference_page_name") or "Original Reference"),
                width_px=float(width_px),
                height_px=float(height_px),
                ppi=self.default_ppi,
            )
            self.pages.append(page)
            self._emit_image_shape(page, {
                "type": "image",
                "name": "Original reference image",
                "x": 0, "y": 0, "w": width_px, "h": height_px,
                "path": str(ref_path),
            }, len(self.pages))
        return self.pages

    def _emit_shape(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        kind = str(shape.get("type") or "rect").lower().replace("-", "_")
        if kind in {"arrow", "double_arrow"}:
            self._emit_arrow(page, shape, page_index)
        elif kind == "image":
            self._emit_image_shape(page, shape, page_index)
        elif kind == "cylinder":
            self._emit_cylinder(page, shape, page_index)
        elif kind == "document":
            self._emit_document(page, shape, page_index)
        elif kind in {"trapezoid", "parallelogram", "triangle", "diamond"}:
            self._emit_semantic_polygon(page, shape, page_index, kind)
        else:
            self._emit_basic_shape(page, shape, page_index)

    def _shape_xform(self, page: PageBuild, x: float, y: float, w: float, h: float, angle_deg: float = 0.0) -> str:
        pin_x = (x + w / 2.0) / page.ppi
        pin_y = (page.height_px - (y + h / 2.0)) / page.ppi
        wi, hi = w / page.ppi, h / page.ppi
        return "".join([
            _cell("PinX", _f(pin_x)),
            _cell("PinY", _f(pin_y)),
            _cell("Width", _f(wi)),
            _cell("Height", _f(hi)),
            _cell("LocPinX", _f(wi / 2.0)),
            _cell("LocPinY", _f(hi / 2.0)),
            _cell("Angle", _f(math.radians(angle_deg))),
        ])

    def _style_cells(self, shape: dict[str, Any]) -> tuple[str, bool, bool]:
        fill_pattern = _fill_pattern(shape)
        line_pattern = _line_pattern(shape)
        fill = _normalize_color(shape.get("fill"), "#FFFFFF")
        line = _normalize_color(shape.get("line") or shape.get("stroke"), "#000000")
        width_px = float(shape.get("line_width_px") or shape.get("stroke_width_px") or 2.0)
        line_weight = max(0.001, width_px / float(shape.get("ppi_override") or self.default_ppi))
        cells = [
            _cell("FillForegnd", fill, formula=_rgb_formula(fill)),
            _cell("FillPattern", fill_pattern),
            _cell("LineColor", line, formula=_rgb_formula(line)),
            _cell("LinePattern", line_pattern),
            _cell("LineWeight", _f(line_weight)),
        ]
        if "fill_transparency" in shape:
            cells.append(_cell("FillForegndTrans", _f(float(shape["fill_transparency"]))))
        if "line_transparency" in shape:
            cells.append(_cell("LineColorTrans", _f(float(shape["line_transparency"]))))
        return "".join(cells), fill_pattern == 0, line_pattern == 0

    def _text_xml(self, shape: dict[str, Any], page: PageBuild) -> str:
        text = shape.get("text")
        if text is None:
            return ""
        style = dict(shape.get("text_style") or {})
        # Shape-level aliases are accepted for concise scene files.
        for key in ("font_family", "font_size_pt", "bold", "italic", "underline", "text_color", "align", "valign"):
            if key in shape and key not in style:
                style[key] = shape[key]
        font_id = self._font_id(style.get("font_family") or style.get("font"))
        color = _normalize_color(style.get("color") or style.get("text_color"), "#000000")
        size_pt = float(style.get("size_pt") or style.get("font_size_pt") or 12.0)
        style_mask = _font_style_mask(style)
        margin_px = float(style.get("margin_px") or 1.5)
        left_margin_px = float(style.get("left_margin_px", margin_px))
        right_margin_px = float(style.get("right_margin_px", margin_px))
        top_margin_px = float(style.get("top_margin_px", margin_px))
        bottom_margin_px = float(style.get("bottom_margin_px", margin_px))
        cells = [
            _cell("VerticalAlign", _vertical_align(style.get("valign"))),
            _cell("LeftMargin", _f(left_margin_px / page.ppi)),
            _cell("RightMargin", _f(right_margin_px / page.ppi)),
            _cell("TopMargin", _f(top_margin_px / page.ppi)),
            _cell("BottomMargin", _f(bottom_margin_px / page.ppi)),
        ]
        char_cells = [
            _cell("Font", font_id),
            _cell("Color", color, formula=_rgb_formula(color)),
            _cell("Size", _f(size_pt / 72.0), unit="PT"),
        ]
        if style_mask:
            char_cells.append(_cell("Style", style_mask))
        if "text_position" in style:
            char_cells.append(_cell("Pos", int(style["text_position"])))
        char_section = '<Section N="Character"><Row IX="0">' + "".join(char_cells) + "</Row></Section>"
        para_section = '<Section N="Paragraph"><Row IX="0">' + _cell("HorzAlign", _horizontal_align(style.get("align"))) + "</Row></Section>"
        return "".join(cells) + char_section + para_section + f"<Text>{_esc(text)}</Text>"

    def _emit_basic_shape(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        kind = str(shape.get("type") or "rect").lower().replace("-", "_")
        name = str(shape.get("name") or f"{kind}-{page.next_shape_id}")
        angle = float(shape.get("angle_deg") or 0.0)

        if kind in {"polyline", "line", "polygon"}:
            points_px = shape.get("points")
            if not points_px or len(points_px) < 2:
                raise ValueError(f"{name}: {kind} requires at least two points")
            x, y, w, h = _shape_bounds_from_points(points_px)
            points_local = _visio_local_points(points_px, x, y, h, page.ppi)
            closed = kind == "polygon" or _bool(shape.get("closed"))
        else:
            x = float(shape.get("x") or 0.0)
            y = float(shape.get("y") or 0.0)
            w = float(shape.get("w") or shape.get("width") or 1.0)
            h = float(shape.get("h") or shape.get("height") or 1.0)
            if w <= 0 or h <= 0:
                raise ValueError(f"{name}: width and height must be positive")
            wi, hi = w / page.ppi, h / page.ppi
            if kind in {"roundrect", "rounded_rect", "rounded_rectangle"}:
                radius_px = float(shape.get("radius_px") or min(w, h) * 0.15)
                points_local = _rounded_rect_points(wi, hi, radius_px / page.ppi, int(shape.get("corner_segments") or 6))
            elif kind == "ellipse":
                points_local = _ellipse_points(wi, hi, int(shape.get("segments") or 48))
            elif kind == "text":
                points_local = _rect_points(wi, hi)
                shape.setdefault("fill", "none")
                shape.setdefault("line", "none")
            else:
                points_local = _rect_points(wi, hi)
            closed = kind not in {"line", "polyline"}

        style_cells, no_fill, no_line = self._style_cells(shape)
        if kind == "text":
            no_fill = True
            no_line = True
        geometry = _geometry_section(points_local, closed=closed, no_fill=no_fill, no_line=no_line)
        xml = (
            f'<Shape ID="__SHAPE_ID__" Name="{_esc(name)}" NameU="{_esc(name)}" Type="Shape" LineStyle="0" FillStyle="0" TextStyle="0">'
            + self._shape_xform(page, x, y, w, h, angle)
            + style_cells
            + geometry
            + self._text_xml(shape, page)
            + "</Shape>"
        )
        page.add_xml_shape(xml)

    def _emit_semantic_polygon(self, page: PageBuild, shape: dict[str, Any], page_index: int, kind: str) -> None:
        x = float(shape.get("x") or 0.0)
        y = float(shape.get("y") or 0.0)
        w = float(shape.get("w") or shape.get("width") or 1.0)
        h = float(shape.get("h") or shape.get("height") or 1.0)
        inset = float(shape.get("inset_px") or min(w * 0.18, h * 0.45))
        if kind == "triangle":
            points = [[x + w / 2, y], [x + w, y + h], [x, y + h]]
        elif kind == "diamond":
            points = [[x + w / 2, y], [x + w, y + h / 2], [x + w / 2, y + h], [x, y + h / 2]]
        elif kind == "parallelogram":
            direction = str(shape.get("slant") or "right").lower()
            if direction == "left":
                points = [[x + inset, y], [x + w, y], [x + w - inset, y + h], [x, y + h]]
            else:
                points = [[x, y], [x + w - inset, y], [x + w, y + h], [x + inset, y + h]]
        else:  # trapezoid
            orientation = str(shape.get("orientation") or "top_narrow").lower()
            if orientation == "left_narrow":
                points = [[x + inset, y], [x + w, y], [x + w, y + h], [x + inset, y + h], [x, y + h / 2]]
            elif orientation == "right_narrow":
                points = [[x, y], [x + w - inset, y], [x + w, y + h / 2], [x + w - inset, y + h], [x, y + h]]
            elif orientation == "bottom_narrow":
                points = [[x, y], [x + w, y], [x + w - inset, y + h], [x + inset, y + h]]
            else:
                points = [[x + inset, y], [x + w - inset, y], [x + w, y + h], [x, y + h]]
        shape = dict(shape)
        shape["type"] = "polygon"
        shape["points"] = points
        self._emit_basic_shape(page, shape, page_index)

    def _emit_arrow(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        points = [[float(p[0]), float(p[1])] for p in shape.get("points", [])]
        if len(points) < 2:
            raise ValueError(f"{shape.get('name','arrow')}: arrow requires at least two points")
        color = _normalize_color(shape.get("line") or shape.get("stroke"), "#000000")
        line_width = float(shape.get("line_width_px") or shape.get("stroke_width_px") or 2.5)
        head_len = float(shape.get("head_length_px") or shape.get("head_size_px") or max(9.0, line_width * 4.0))
        head_width = float(shape.get("head_width_px") or head_len * 0.9)
        end_head = _bool(shape.get("end_head"), True)
        start_head = _bool(shape.get("start_head"), str(shape.get("type")).lower() == "double_arrow")
        base_name = str(shape.get("name") or f"Arrow {page.next_shape_id}")

        def triangle_for(p0: Sequence[float], p1: Sequence[float]) -> tuple[list[list[float]], list[float]]:
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            length = math.hypot(dx, dy)
            if length < 1e-9:
                raise ValueError(f"{base_name}: arrow endpoint segment has zero length")
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            base = [p1[0] - ux * head_len, p1[1] - uy * head_len]
            tri = [
                [p1[0], p1[1]],
                [base[0] + px * head_width / 2.0, base[1] + py * head_width / 2.0],
                [base[0] - px * head_width / 2.0, base[1] - py * head_width / 2.0],
            ]
            return tri, base

        line_points = [p[:] for p in points]
        triangles: list[tuple[str, list[list[float]]]] = []
        if end_head:
            tri, base = triangle_for(points[-2], points[-1])
            line_points[-1] = base
            triangles.append((base_name + " head", tri))
        if start_head:
            tri, base = triangle_for(points[1], points[0])
            line_points[0] = base
            triangles.append((base_name + " start head", tri))

        line_shape = {
            "type": "polyline",
            "name": base_name + " line",
            "points": line_points,
            "fill": "none",
            "line": color,
            "line_width_px": line_width,
            "dash": shape.get("dash"),
        }
        self._emit_basic_shape(page, line_shape, page_index)
        for name, tri in triangles:
            self._emit_basic_shape(page, {
                "type": "polygon",
                "name": name,
                "points": tri,
                "fill": color,
                "line": color,
                "line_width_px": max(0.5, line_width * 0.45),
            }, page_index)

    def _load_image_bytes(self, shape: dict[str, Any]) -> bytes:
        if Image is None:
            raise RuntimeError("Pillow is required for image shapes")
        path_raw = shape.get("path") or shape.get("source") or self.scene.get("reference_image")
        if not path_raw:
            raise ValueError(f"{shape.get('name','image')}: image path/source is required")
        path = self._resolve_path(str(path_raw))
        if not path.exists():
            raise FileNotFoundError(f"image not found: {path}")
        with Image.open(path) as im:
            im = im.convert("RGBA")
            crop = shape.get("crop") or shape.get("crop_px")
            crop_box = shape.get("crop_box")
            if crop:
                if len(crop) != 4:
                    raise ValueError("crop must be [x, y, width, height]")
                cx, cy, cw, ch = map(float, crop)
                im = im.crop((round(cx), round(cy), round(cx + cw), round(cy + ch)))
            elif crop_box:
                if len(crop_box) != 4:
                    raise ValueError("crop_box must be [left, top, right, bottom]")
                im = im.crop(tuple(round(float(v)) for v in crop_box))
            if _bool(shape.get("grayscale")):
                im = im.convert("L").convert("RGBA")
            alpha = shape.get("alpha")
            if alpha is not None:
                factor = max(0.0, min(1.0, float(alpha)))
                a = im.getchannel("A").point(lambda p: round(p * factor))
                im.putalpha(a)
            buffer = io.BytesIO()
            im.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()

    def _emit_image_shape(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        name = str(shape.get("name") or f"Image {page.next_shape_id}")
        x = float(shape.get("x") or 0.0)
        y = float(shape.get("y") or 0.0)
        w = shape.get("w") or shape.get("width")
        h = shape.get("h") or shape.get("height")
        path_raw = shape.get("path") or shape.get("source") or self.scene.get("reference_image")
        if (w is None or h is None) and path_raw:
            if Image is None:
                raise RuntimeError("Pillow is required to infer image dimensions")
            with Image.open(self._resolve_path(str(path_raw))) as im:
                iw, ih = im.size
            crop = shape.get("crop") or shape.get("crop_px")
            if crop:
                iw, ih = float(crop[2]), float(crop[3])
            w = iw if w is None else w
            h = ih if h is None else h
        w = float(w or 1.0)
        h = float(h or 1.0)
        if w <= 0 or h <= 0:
            raise ValueError(f"{name}: image width and height must be positive")
        data = self._load_image_bytes(shape)
        media = page.add_media(data, page_index)
        angle = float(shape.get("angle_deg") or 0.0)
        wi, hi = w / page.ppi, h / page.ppi
        xml = (
            f'<Shape ID="__SHAPE_ID__" Name="{_esc(name)}" NameU="{_esc(name)}" Type="Foreign" LineStyle="0" FillStyle="0" TextStyle="0">'
            + self._shape_xform(page, x, y, w, h, angle)
            + _cell("LinePattern", 0)
            + _cell("FillPattern", 0)
            + _cell("ImgOffsetX", 0)
            + _cell("ImgOffsetY", 0)
            + _cell("ImgWidth", _f(wi))
            + _cell("ImgHeight", _f(hi))
            + f'<ForeignData ForeignType="Bitmap" CompressionType="PNG"><Rel r:id="{media.rel_id}"/></ForeignData>'
            + "</Shape>"
        )
        page.add_xml_shape(xml)

    def _emit_cylinder(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        x = float(shape.get("x") or 0.0)
        y = float(shape.get("y") or 0.0)
        w = float(shape.get("w") or shape.get("width") or 1.0)
        h = float(shape.get("h") or shape.get("height") or 1.0)
        eh = float(shape.get("ellipse_height_px") or min(h * 0.24, w * 0.34))
        segments = int(shape.get("segments") or 18)
        pts: list[list[float]] = []
        # Top upper half: left -> top -> right.
        cx, top_cy = x + w / 2.0, y + eh / 2.0
        for i in range(segments + 1):
            a = math.pi + math.pi * i / segments
            pts.append([cx + (w / 2.0) * math.cos(a), top_cy + (eh / 2.0) * math.sin(a)])
        # Right wall, then bottom lower half: right -> bottom -> left.
        bottom_cy = y + h - eh / 2.0
        pts.append([x + w, bottom_cy])
        for i in range(segments + 1):
            a = 0.0 + math.pi * i / segments
            pts.append([cx + (w / 2.0) * math.cos(a), bottom_cy + (eh / 2.0) * math.sin(a)])
        pts.append([x, top_cy])
        outer = dict(shape)
        outer["type"] = "polygon"
        outer["name"] = str(shape.get("name") or "Cylinder")
        outer["points"] = pts
        self._emit_basic_shape(page, outer, page_index)
        # Top ellipse outline preserves the familiar memory-bank/database look.
        outline_pts: list[list[float]] = []
        for i in range(48):
            a = 2 * math.pi * i / 48
            outline_pts.append([cx + (w / 2.0) * math.cos(a), top_cy + (eh / 2.0) * math.sin(a)])
        self._emit_basic_shape(page, {
            "type": "polygon",
            "name": str(shape.get("name") or "Cylinder") + " top ellipse",
            "points": outline_pts,
            "fill": "none",
            "line": shape.get("line") or shape.get("stroke") or "#17335D",
            "line_width_px": shape.get("line_width_px") or 2.5,
        }, page_index)

    def _emit_document(self, page: PageBuild, shape: dict[str, Any], page_index: int) -> None:
        x = float(shape.get("x") or 0.0)
        y = float(shape.get("y") or 0.0)
        w = float(shape.get("w") or shape.get("width") or 1.0)
        h = float(shape.get("h") or shape.get("height") or 1.0)
        wave_h = float(shape.get("wave_height_px") or h * 0.14)
        wave_cycles = float(shape.get("wave_cycles") or 1.25)
        points: list[list[float]] = [[x, y], [x + w, y], [x + w, y + h - wave_h]]
        samples = int(shape.get("wave_samples") or 24)
        for i in range(samples + 1):
            t = i / samples
            px = x + w * (1.0 - t)
            py = y + h - wave_h / 2.0 + math.sin(t * wave_cycles * 2 * math.pi) * wave_h / 2.0
            points.append([px, py])
        points.append([x, y])
        doc_shape = dict(shape)
        doc_shape["type"] = "polygon"
        doc_shape["points"] = points
        self._emit_basic_shape(page, doc_shape, page_index)

    def _document_xml(self) -> str:
        face_names = "".join(f'<FaceName NameU="{_esc(name)}"/>' for name in self.font_names)
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<VisioDocument xmlns="{VISIO_NS}" xmlns:r="{REL_NS}">
  <DocumentSettings TopPage="0" DefaultTextStyle="0" DefaultLineStyle="0" DefaultFillStyle="0" DefaultGuideStyle="4">
    <GlueSettings>9</GlueSettings><SnapSettings>295</SnapSettings><SnapExtensions>34</SnapExtensions><SnapAngles/>
    <DynamicGridEnabled>1</DynamicGridEnabled><ProtectStyles>0</ProtectStyles><ProtectShapes>0</ProtectShapes><ProtectMasters>0</ProtectMasters><ProtectBkgnds>0</ProtectBkgnds>
  </DocumentSettings>
  <Colors/><FaceNames>{face_names}</FaceNames>
  <StyleSheets>
    <StyleSheet ID="0" Name="No Style" NameU="No Style"><Cell N="EnableLineProps" V="1"/><Cell N="EnableFillProps" V="1"/><Cell N="EnableTextProps" V="1"/><Cell N="LineWeight" V="0.01041666666666667"/><Cell N="LineColor" V="0"/><Cell N="LinePattern" V="1"/><Cell N="FillForegnd" V="1"/><Cell N="FillPattern" V="1"/><Cell N="TextBkgnd" V="0"/></StyleSheet>
    <StyleSheet ID="1" Name="Normal" NameU="Normal" BasedOn="0" LineStyle="0" FillStyle="0" TextStyle="0"><Cell N="LinePattern" V="1"/><Cell N="LineColor" V="#000000"/><Cell N="FillPattern" V="1"/><Cell N="FillForegnd" V="#FFFFFF"/></StyleSheet>
    <StyleSheet ID="2" Name="Connector" NameU="Connector" BasedOn="1" LineStyle="0" FillStyle="0" TextStyle="0"><Cell N="EndArrow" V="0"/></StyleSheet>
  </StyleSheets>
</VisioDocument>'''

    def _pages_xml(self) -> str:
        chunks = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Pages xmlns="{VISIO_NS}" xmlns:r="{REL_NS}" xml:space="preserve">']
        for i, page in enumerate(self.pages):
            chunks.append(
                f'<Page ID="{i}" Name="{_esc(page.name)}" NameU="{_esc(page.name)}" ViewScale="1" ViewCenterX="{_f(page.width_in/2)}" ViewCenterY="{_f(page.height_in/2)}">'
                '<PageSheet LineStyle="0" FillStyle="0" TextStyle="0">'
                + _cell("PageWidth", _f(page.width_in))
                + _cell("PageHeight", _f(page.height_in))
                + _cell("ShdwOffsetX", "0.1181102362204724")
                + _cell("ShdwOffsetY", "-0.1181102362204724")
                + _cell("PageScale", 1)
                + _cell("DrawingScale", 1)
                + _cell("DrawingSizeType", 0)
                + _cell("DrawingScaleType", 0)
                + _cell("InhibitSnap", 0)
                + _cell("PageLockReplace", 0, unit="BOOL")
                + _cell("PageLockDuplicate", 0, unit="BOOL")
                + _cell("UIVisibility", 0)
                + _cell("ShdwType", 0)
                + _cell("ShdwObliqueAngle", 0)
                + _cell("ShdwScaleFactor", 1)
                + _cell("DrawingResizeType", 0)
                + f'</PageSheet><Rel r:id="rId{i+1}"/></Page>'
            )
        chunks.append("</Pages>")
        return "".join(chunks)

    def _page_xml(self, page: PageBuild) -> str:
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><PageContents xmlns="{VISIO_NS}" xmlns:r="{REL_NS}" xml:space="preserve"><Shapes>{"".join(page.xml_shapes)}</Shapes></PageContents>'

    def write(self, output_path: Path) -> dict[str, Any]:
        if not self.pages:
            self.build()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        now = self.created_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        page_overrides = "".join(
            f'<Override PartName="/visio/pages/page{i+1}.xml" ContentType="application/vnd.ms-visio.page+xml"/>'
            for i in range(len(self.pages))
        )
        content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{CONTENT_TYPE_NS}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/><Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>{page_overrides}<Override PartName="/visio/windows.xml" ContentType="application/vnd.ms-visio.windows+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''
        root_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'''
        document_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/visio/2010/relationships/windows" Target="windows.xml"/></Relationships>'''
        pages_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}">{''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page{i+1}.xml"/>' for i in range(len(self.pages)))}</Relationships>'''
        first = self.pages[0]
        windows_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Windows xmlns="{VISIO_NS}" xmlns:r="{REL_NS}" ClientWidth="1000" ClientHeight="700"><Window ID="0" WindowType="Drawing" WindowState="1073741824" WindowLeft="0" WindowTop="0" WindowWidth="1000" WindowHeight="700" ContainerType="Page" Page="0" ViewScale="1" ViewCenterX="{_f(first.width_in/2)}" ViewCenterY="{_f(first.height_in/2)}"/></Windows>'''
        core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{_esc(self.title)}</dc:title><dc:creator>{_esc(self.author)}</dc:creator><cp:lastModifiedBy>{_esc(self.author)}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'''
        app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Visio</Application><AppVersion>16.0000</AppVersion></Properties>'''

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            def write_part(name: str, data: str | bytes) -> None:
                if self.deterministic_zip_timestamps:
                    info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                else:
                    zf.writestr(name, data)

            write_part("[Content_Types].xml", content_types)
            write_part("_rels/.rels", root_rels)
            write_part("docProps/core.xml", core_xml)
            write_part("docProps/app.xml", app_xml)
            write_part("visio/document.xml", self._document_xml())
            write_part("visio/_rels/document.xml.rels", document_rels)
            write_part("visio/windows.xml", windows_xml)
            write_part("visio/pages/pages.xml", self._pages_xml())
            write_part("visio/pages/_rels/pages.xml.rels", pages_rels)
            for i, page in enumerate(self.pages, start=1):
                write_part(f"visio/pages/page{i}.xml", self._page_xml(page))
                if page.media:
                    rels = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}">' + "".join(
                        f'<Relationship Id="{m.rel_id}" Type="{IMAGE_REL_TYPE}" Target="../media/{_esc(m.filename)}"/>' for m in page.media
                    ) + "</Relationships>"
                    write_part(f"visio/pages/_rels/page{i}.xml.rels", rels)
                    for media in page.media:
                        write_part(f"visio/media/{media.filename}", media.data)

        manifest = {
            "output": str(output_path),
            "title": self.title,
            "author": self.author,
            "pages": [
                {
                    "name": p.name,
                    "width_px": p.width_px,
                    "height_px": p.height_px,
                    "ppi": p.ppi,
                    "shape_count": len(p.xml_shapes),
                    "image_count": len(p.media),
                }
                for p in self.pages
            ],
            "fonts": self.font_names,
            "warnings": self.warnings,
        }
        return manifest


def load_scene(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_scene(scene_path: Path, output_path: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    scene = load_scene(scene_path)
    builder = VsdxSceneBuilder(scene, scene_path=scene_path)
    builder.build()
    manifest = builder.write(output_path)
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an editable VSDX from a JSON scene.")
    parser.add_argument("scene", type=Path, help="Path to scene JSON")
    parser.add_argument("output", type=Path, help="Output .vsdx path")
    parser.add_argument("--manifest", type=Path, help="Optional manifest JSON path")
    args = parser.parse_args(argv)
    try:
        manifest = build_scene(args.scene, args.output, args.manifest)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

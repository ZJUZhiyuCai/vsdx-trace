#!/usr/bin/env python3
"""Generate a deterministic, privacy-safe Visio reconstruction benchmark.

The example contains only synthetic labels, vector geometry, and procedurally
created abstract raster frames. It does not reuse any user-uploaded image,
conversation content, personal identifier, organization, paper title, logo, or
private file path.

Typical usage:

    python examples/synthetic_event_routing_case.py \
      --work-dir work/synthetic-event-routing \
      --output work/synthetic-event-routing/synthetic_event_routing_editable.vsdx

The script writes the reference PNG, local raster media, scene JSON, VSDX, and
build manifest. Run scripts/validate_vsdx.py, scripts/render_vsdx.py, and
scripts/compare_images.py afterward for the full QA loop.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vsdx_builder import build_scene as build_vsdx_scene  # noqa: E402

WIDTH = 1600
HEIGHT = 1000
PPI = 100

NAVY = "#1F3A63"
BLUE = "#315D8D"
PALE = "#F1F5FA"
LIGHT_BLUE = "#CFDCEE"
LIGHTER_BLUE = "#E8EEF7"
RED = "#B53B32"
PALE_RED = "#F5DFDD"
GREEN = "#86AE6B"
PALE_GREEN = "#DFEBD6"
GRAY = "#6D7480"
LIGHT_GRAY = "#E7E9ED"
BLACK = "#111111"
WHITE = "#FFFFFF"


def _font_path(bold: bool = False) -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _font(size_pt: float, bold: bool = False) -> ImageFont.ImageFont:
    size_px = max(8, round(size_pt * PPI / 72))
    path = _font_path(bold)
    if path:
        return ImageFont.truetype(path, size_px)
    return ImageFont.load_default()


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _shape_text_style(
    size: float = 12,
    *,
    bold: bool = False,
    color: str = BLACK,
    align: str = "center",
    valign: str = "middle",
    margin: float = 1.5,
) -> dict[str, Any]:
    return {
        "font_family": "Arial",
        "size_pt": size,
        "bold": bold,
        "color": color,
        "align": align,
        "valign": valign,
        "margin_px": margin,
    }


class Scene:
    def __init__(self) -> None:
        self.shapes: list[dict[str, Any]] = []

    def add(self, shape: dict[str, Any]) -> dict[str, Any]:
        self.shapes.append(shape)
        return shape

    def rect(self, name: str, x: float, y: float, w: float, h: float, **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "rect", "name": name, "x": x, "y": y, "w": w, "h": h, **kwargs})

    def roundrect(self, name: str, x: float, y: float, w: float, h: float, **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "roundrect", "name": name, "x": x, "y": y, "w": w, "h": h, **kwargs})

    def ellipse(self, name: str, x: float, y: float, w: float, h: float, **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "ellipse", "name": name, "x": x, "y": y, "w": w, "h": h, **kwargs})

    def text(self, name: str, x: float, y: float, w: float, h: float, text: str, **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "text", "name": name, "x": x, "y": y, "w": w, "h": h, "text": text, **kwargs})

    def arrow(self, name: str, points: list[list[float]], **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "arrow", "name": name, "points": points, **kwargs})

    def polygon(self, name: str, points: list[list[float]], **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "polygon", "name": name, "points": points, **kwargs})

    def image(self, name: str, x: float, y: float, w: float, h: float, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.add({"type": "image", "name": name, "x": x, "y": y, "w": w, "h": h, "path": path, **kwargs})


def _make_abstract_frame(path: Path, seed: int, width: int = 260, height: int = 150) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height), _hex("#E8EDF3"))
    draw = ImageDraw.Draw(image)
    # Horizon and lanes: abstract geometry only, no real person or location.
    draw.rectangle((0, 0, width, height // 2), fill=_hex("#DDE6EE"))
    draw.rectangle((0, height // 2, width, height), fill=_hex("#C8CDD2"))
    draw.polygon([(width * 0.40, height), (width * 0.48, height // 2), (width * 0.54, height // 2), (width * 0.68, height)], fill=_hex("#AEB5BC"))
    for offset in (-30, 15, 60):
        draw.line((width // 2 + offset, height, width // 2 + offset // 4, height // 2), fill=_hex("#F4F5F6"), width=3)
    # Synthetic event markers.
    cx = 72 + (seed * 17) % 130
    cy = 70 + (seed * 11) % 45
    size = 16 + (seed * 3) % 12
    draw.rounded_rectangle((cx - size, cy - size, cx + size, cy + size), radius=6, fill=_hex("#C5685C"), outline=_hex("#7A342C"), width=2)
    draw.ellipse((cx + size + 8, cy - 8, cx + size + 24, cy + 8), fill=_hex("#4B6E8F"))
    # Deterministic subtle noise.
    for _ in range(90):
        x = rng.randrange(width)
        y = rng.randrange(height)
        v = rng.randrange(195, 230)
        draw.point((x, y), fill=(v, v, v))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _dashed_line(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], fill: tuple[int, int, int], width: int, dash: int = 10, gap: int = 8) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return
    ux = (x2 - x1) / length
    uy = (y2 - y1) / length
    pos = 0.0
    while pos < length:
        e = min(length, pos + dash)
        draw.line((x1 + ux * pos, y1 + uy * pos, x1 + ux * e, y1 + uy * e), fill=fill, width=width)
        pos += dash + gap


def _draw_dashed_rect(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], fill: tuple[int, int, int], width: int) -> None:
    x1, y1, x2, y2 = box
    _dashed_line(draw, (x1, y1), (x2, y1), fill, width)
    _dashed_line(draw, (x2, y1), (x2, y2), fill, width)
    _dashed_line(draw, (x2, y2), (x1, y2), fill, width)
    _dashed_line(draw, (x1, y2), (x1, y1), fill, width)


def _draw_text(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], text: str, style: dict[str, Any]) -> None:
    x, y, w, h = box
    font = _font(float(style.get("size_pt", 12)), bool(style.get("bold", False)))
    fill = _hex(str(style.get("color", BLACK)))
    align = str(style.get("align", "center"))
    valign = str(style.get("valign", "middle"))
    spacing = max(2, round(float(style.get("size_pt", 12)) * 0.2))
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align=align)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    margin = float(style.get("margin_px", 1.5))
    if align == "left":
        tx = x + margin
    elif align == "right":
        tx = x + w - tw - margin
    else:
        tx = x + (w - tw) / 2
    if valign == "top":
        ty = y + margin
    elif valign == "bottom":
        ty = y + h - th - margin
    else:
        ty = y + (h - th) / 2 - bbox[1]
    draw.multiline_text((tx, ty), text, font=font, fill=fill, spacing=spacing, align=align)


def _render_scene(scene: dict[str, Any], scene_path: Path, output: Path) -> None:
    canvas = scene["canvas"]
    image = Image.new("RGB", (int(canvas["width_px"]), int(canvas["height_px"])), _hex(canvas.get("background", WHITE)))
    draw = ImageDraw.Draw(image)
    base = scene_path.parent

    for shape in scene["pages"][0]["shapes"]:
        kind = shape["type"]
        fill_raw = shape.get("fill", "none")
        line_raw = shape.get("line", "none")
        fill = None if fill_raw in {None, "none", "transparent"} else _hex(str(fill_raw))
        line = None if line_raw in {None, "none", "transparent"} else _hex(str(line_raw))
        lw = max(1, round(float(shape.get("line_width_px", 2))))

        if kind in {"rect", "roundrect", "ellipse", "text", "cylinder", "document", "trapezoid", "parallelogram", "triangle", "diamond", "image"}:
            x = float(shape.get("x", 0))
            y = float(shape.get("y", 0))
            w = float(shape.get("w", 1))
            h = float(shape.get("h", 1))
            box = (x, y, x + w, y + h)
        if kind == "rect":
            if fill:
                draw.rectangle(box, fill=fill)
            if line:
                if shape.get("dash"):
                    _draw_dashed_rect(draw, box, line, lw)
                else:
                    draw.rectangle(box, outline=line, width=lw)
        elif kind == "roundrect":
            radius = max(1, round(float(shape.get("radius_px", min(w, h) * 0.15))))
            if fill:
                draw.rounded_rectangle(box, radius=radius, fill=fill)
            if line:
                if shape.get("dash"):
                    _draw_dashed_rect(draw, box, line, lw)
                else:
                    draw.rounded_rectangle(box, radius=radius, outline=line, width=lw)
        elif kind == "ellipse":
            if fill:
                draw.ellipse(box, fill=fill)
            if line:
                draw.ellipse(box, outline=line, width=lw)
        elif kind == "text":
            pass
        elif kind == "image":
            source = Path(shape["path"])
            if not source.is_absolute():
                source = (base / source).resolve()
            with Image.open(source) as src:
                src = src.convert("RGB").resize((round(w), round(h)), Image.Resampling.LANCZOS)
                image.paste(src, (round(x), round(y)))
        elif kind in {"polygon", "polyline", "line", "arrow"}:
            points = [(float(a), float(b)) for a, b in shape["points"]]
            if kind == "polygon":
                if fill:
                    draw.polygon(points, fill=fill)
                if line:
                    draw.line(points + [points[0]], fill=line, width=lw, joint="curve")
            elif kind in {"polyline", "line"}:
                if line:
                    draw.line(points, fill=line, width=lw, joint="curve")
            else:
                color = line or _hex(BLACK)
                head_len = float(shape.get("head_length_px", max(9, lw * 4)))
                head_width = float(shape.get("head_width_px", head_len * 0.9))
                p0 = points[-2]
                p1 = points[-1]
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                length = max(1e-6, math.hypot(dx, dy))
                ux, uy = dx / length, dy / length
                px, py = -uy, ux
                base_pt = (p1[0] - ux * head_len, p1[1] - uy * head_len)
                line_points = points[:-1] + [base_pt]
                draw.line(line_points, fill=color, width=lw, joint="curve")
                tri = [p1, (base_pt[0] + px * head_width / 2, base_pt[1] + py * head_width / 2), (base_pt[0] - px * head_width / 2, base_pt[1] - py * head_width / 2)]
                draw.polygon(tri, fill=color)
        elif kind == "cylinder":
            eh = float(shape.get("ellipse_height_px", min(h * 0.24, w * 0.34)))
            body_box = (x, y + eh / 2, x + w, y + h - eh / 2)
            if fill:
                draw.rectangle(body_box, fill=fill)
                draw.ellipse((x, y, x + w, y + eh), fill=fill)
                draw.ellipse((x, y + h - eh, x + w, y + h), fill=fill)
            if line:
                draw.line((x, y + eh / 2, x, y + h - eh / 2), fill=line, width=lw)
                draw.line((x + w, y + eh / 2, x + w, y + h - eh / 2), fill=line, width=lw)
                draw.arc((x, y, x + w, y + eh), 0, 360, fill=line, width=lw)
                draw.arc((x, y + h - eh, x + w, y + h), 0, 180, fill=line, width=lw)
        elif kind == "trapezoid":
            inset = float(shape.get("inset_px", min(w * 0.18, h * 0.45)))
            orientation = str(shape.get("orientation", "top_narrow"))
            if orientation == "right_narrow":
                pts = [(x, y), (x + w - inset, y), (x + w, y + h / 2), (x + w - inset, y + h), (x, y + h)]
            elif orientation == "left_narrow":
                pts = [(x + inset, y), (x + w, y), (x + w, y + h), (x + inset, y + h), (x, y + h / 2)]
            elif orientation == "bottom_narrow":
                pts = [(x, y), (x + w, y), (x + w - inset, y + h), (x + inset, y + h)]
            else:
                pts = [(x + inset, y), (x + w - inset, y), (x + w, y + h), (x, y + h)]
            if fill:
                draw.polygon(pts, fill=fill)
            if line:
                draw.line(pts + [pts[0]], fill=line, width=lw)
        elif kind == "parallelogram":
            inset = float(shape.get("inset_px", min(w * 0.18, h * 0.45)))
            pts = [(x, y), (x + w - inset, y), (x + w, y + h), (x + inset, y + h)]
            if fill:
                draw.polygon(pts, fill=fill)
            if line:
                draw.line(pts + [pts[0]], fill=line, width=lw)
        elif kind == "triangle":
            pts = [(x + w / 2, y), (x + w, y + h), (x, y + h)]
            if fill:
                draw.polygon(pts, fill=fill)
            if line:
                draw.line(pts + [pts[0]], fill=line, width=lw)
        elif kind == "diamond":
            pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            if fill:
                draw.polygon(pts, fill=fill)
            if line:
                draw.line(pts + [pts[0]], fill=line, width=lw)
        elif kind == "document":
            wave = float(shape.get("wave_height_px", h * 0.14))
            pts = [(x, y), (x + w, y), (x + w, y + h - wave)]
            samples = 24
            cycles = float(shape.get("wave_cycles", 1.25))
            for i in range(samples + 1):
                t = i / samples
                pts.append((x + w * (1 - t), y + h - wave / 2 + math.sin(t * cycles * 2 * math.pi) * wave / 2))
            pts.append((x, y))
            if fill:
                draw.polygon(pts, fill=fill)
            if line:
                draw.line(pts + [pts[0]], fill=line, width=lw)

        text = shape.get("text")
        if text is not None:
            _draw_text(draw, (x, y, w, h), str(text), dict(shape.get("text_style") or {}))

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def _add_warning(scene: Scene, name: str, x: float, y: float, size: float = 38) -> None:
    scene.add({
        "type": "triangle",
        "name": f"{name} triangle",
        "x": x,
        "y": y,
        "w": size,
        "h": size,
        "fill": PALE_RED,
        "line": RED,
        "line_width_px": 3,
    })
    scene.text(
        f"{name} mark",
        x + size * 0.30,
        y + size * 0.20,
        size * 0.40,
        size * 0.55,
        "!",
        text_style=_shape_text_style(15, bold=True),
    )


def _add_prohibit(scene: Scene, name: str, x: float, y: float, size: float = 30) -> None:
    scene.ellipse(name + " ring", x, y, size, size, fill="none", line=RED, line_width_px=3)
    scene.add({
        "type": "polyline",
        "name": name + " slash",
        "points": [[x + 5, y + 5], [x + size - 5, y + size - 5]],
        "fill": "none",
        "line": RED,
        "line_width_px": 3,
    })


def build_scene(work_dir: Path) -> tuple[dict[str, Any], Path, Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    media_dir = work_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 13):
        _make_abstract_frame(media_dir / f"abstract_frame_{index:02d}.png", seed=index)

    scene = Scene()
    # Page and top diagnosis panel.
    scene.roundrect("Diagnosis background", 8, 8, 1584, 300, radius_px=26, fill="#EEF2F8", line="none")
    scene.text("Main title", 500, 5, 600, 45, "Reliability Diagnosis", text_style=_shape_text_style(23, bold=True))
    scene.roundrect("Baseline failure panel", 25, 52, 745, 238, radius_px=24, fill="none", line=BLUE, line_width_px=3, dash=True)
    scene.roundrect("Protected routing panel", 790, 52, 785, 238, radius_px=24, fill="none", line=BLUE, line_width_px=3, dash=True)
    scene.text("Baseline title", 85, 57, 620, 35, "baseline event-retrieval failure", text_style=_shape_text_style(17))
    scene.text("Protected title", 905, 57, 555, 35, "confidence-preserving event routing", text_style=_shape_text_style(17))

    # Left/top: synthetic stale-event stack and collision.
    for i in range(5):
        x = 65 + i * 28
        y = 110 + i * 14
        scene.rect(f"Stale frame border {i+1}", x - 2, y - 2, 142, 83, fill=WHITE, line=GRAY, line_width_px=1)
        scene.image(f"Stale frame {i+1}", x, y, 138, 79, f"media/abstract_frame_{i+1:02d}.png", grayscale=i < 4, alpha=0.68 if i < 4 else 1.0)
    scene.arrow("Stale stack to candidates", [[245, 171], [340, 171]], line=BLACK, line_width_px=3, head_length_px=16)
    token_y = 100
    for i, (label, color) in enumerate([
        ("event A", NAVY), ("event B", NAVY), ("event C", NAVY), ("event D", RED), ("event E", RED)
    ]):
        scene.roundrect(
            f"Candidate token {i+1}", 372, token_y + i * 34, 105, 29,
            radius_px=7, fill=LIGHTER_BLUE if color == NAVY else PALE_RED,
            line=color, line_width_px=2, text=label,
            text_style=_shape_text_style(11, color=BLACK),
        )
    scene.text("Collision formula left", 500, 125, 140, 42, "score = Σ", text_style=_shape_text_style(16, align="left"))
    scene.text("Collision formula middle", 620, 125, 78, 42, "high", text_style=_shape_text_style(16, color=RED, align="left"))
    scene.text("Collision formula right", 693, 125, 55, 42, "risk", text_style=_shape_text_style(16, align="left"))
    scene.text("Stale events label", 60, 245, 185, 30, "stale events", text_style=_shape_text_style(14, color=RED))
    scene.text("Spurious matches label", 245, 245, 230, 30, "spurious matches", text_style=_shape_text_style(14, color=RED))
    scene.text("Collision label", 505, 230, 185, 45, "retrieval\ncollision", text_style=_shape_text_style(14, color=RED))
    scene.add({"type": "polyline", "name": "Stale label leader", "points": [[135, 237], [165, 195]], "line": RED, "line_width_px": 2, "fill": "none"})
    scene.add({"type": "polyline", "name": "Spurious label leader", "points": [[335, 238], [310, 196]], "line": RED, "line_width_px": 2, "fill": "none"})
    scene.add({"type": "polyline", "name": "Collision label leader", "points": [[540, 229], [475, 184]], "line": RED, "line_width_px": 2, "fill": "none"})

    # Right/top: routing through a memory bank and query evidence.
    scene.add({
        "type": "cylinder", "name": "Protected memory bank", "x": 835, "y": 105, "w": 170, "h": 105,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Memory\nBank", "text_style": _shape_text_style(17),
    })
    _add_warning(scene, "Upper uncertainty warning", 995, 87, 42)
    _add_warning(scene, "Lower uncertainty warning", 980, 188, 42)
    scene.arrow("Bank to gate", [[1015, 158], [1085, 158]], line=BLACK, line_width_px=3, head_length_px=15)
    scene.roundrect("Confidence gate", 1090, 127, 49, 56, radius_px=10, fill=LIGHT_BLUE, line=NAVY, line_width_px=3, text="g", text_style=_shape_text_style(19, bold=True))
    scene.arrow("Gate to protected tokens", [[1142, 158], [1205, 158]], line=BLACK, line_width_px=3, head_length_px=15)
    for i, color in enumerate([NAVY, NAVY, NAVY, GREEN]):
        scene.roundrect(
            f"Protected token {i+1}", 1218, 92 + i * 36, 100, 30,
            radius_px=6, fill=LIGHTER_BLUE if color == NAVY else PALE_GREEN,
            line=color, line_width_px=2, text="event" if i < 2 else ("..." if i == 2 else "focus"),
            text_style=_shape_text_style(11),
        )
    scene.text("Plus sign top", 1336, 131, 40, 50, "+", text_style=_shape_text_style(23, bold=True))
    scene.rect("Query frame border", 1387, 110, 150, 88, fill=WHITE, line=BLACK, line_width_px=2)
    scene.image("Query-specific evidence", 1390, 113, 144, 82, "media/abstract_frame_09.png")
    scene.text("Compressed context label", 835, 218, 360, 60, "Compressed Temporal\nContext", text_style=_shape_text_style(16))
    scene.text("Query evidence label", 1325, 218, 235, 60, "Query-Specific\nEvidence", text_style=_shape_text_style(16))
    scene.text("Routing label", 1035, 88, 145, 38, "routing\ngate", text_style=_shape_text_style(12))

    # Middle pipeline: history clips, current clip, encoders, router, reasoner and outputs.
    history_positions = [(58, 350), (58, 435), (58, 520), (58, 605)]
    for i, (x, y) in enumerate(history_positions):
        scene.rect(f"History frame border {i+1}", x - 2, y - 2, 120, 70, fill=WHITE, line=GRAY, line_width_px=1)
        scene.image(f"History frame {i+1}", x, y, 116, 66, f"media/abstract_frame_{i+1:02d}.png", grayscale=i != 2, alpha=0.72 if i != 2 else 1.0)
    scene.add({"type": "polyline", "name": "History bracket", "points": [[182, 365], [198, 365], [198, 654], [182, 654]], "line": BLACK, "line_width_px": 3, "fill": "none"})
    scene.arrow("History to current stack", [[198, 510], [248, 510]], line=BLACK, line_width_px=3, head_length_px=14)
    for i in range(4):
        x = 250 + i * 14
        y = 468 + i * 10
        scene.rect(f"Current stack border {i+1}", x - 2, y - 2, 136, 81, fill=WHITE, line=GRAY, line_width_px=1)
        scene.image(f"Current stack frame {i+1}", x, y, 132, 77, f"media/abstract_frame_{6+i:02d}.png", grayscale=i < 3, alpha=0.65 if i < 3 else 1.0)
    scene.arrow("Current stack to video encoder", [[425, 530], [480, 530]], line=BLACK, line_width_px=3, head_length_px=15)
    scene.add({
        "type": "trapezoid", "name": "Video encoder", "x": 485, "y": 410, "w": 165, "h": 225,
        "orientation": "right_narrow", "inset_px": 40,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Video\nEncoder", "text_style": _shape_text_style(20),
    })
    scene.arrow("Video encoder to memory router", [[653, 530], [710, 530]], line=BLACK, line_width_px=3, head_length_px=15)
    scene.add({
        "type": "roundrect", "name": "Memory router", "x": 715, "y": 475, "w": 185, "h": 110,
        "radius_px": 24, "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Memory\nRouter", "text_style": _shape_text_style(19),
    })
    scene.add({
        "type": "cylinder", "name": "Compressed memory bank", "x": 735, "y": 330, "w": 165, "h": 92,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
    })
    scene.text("Compressed bank label", 915, 332, 240, 80, "Compressed\nMemory Bank", text_style=_shape_text_style(17, align="left"))
    scene.arrow("Bank gate one", [[790, 421], [790, 474]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.arrow("Bank gate two", [[835, 421], [835, 474]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.text("Gates label", 680, 420, 100, 40, "gates", text_style=_shape_text_style(16))
    scene.roundrect("Small gate icon", 858, 432, 38, 34, radius_px=8, fill=LIGHT_BLUE, line=NAVY, line_width_px=2, text="g", text_style=_shape_text_style(13, bold=True))
    scene.arrow("Memory router to temporal analyzer", [[900, 530], [965, 530]], line=BLACK, line_width_px=3, head_length_px=15)
    scene.add({
        "type": "roundrect", "name": "Temporal analyzer", "x": 970, "y": 475, "w": 190, "h": 110,
        "radius_px": 24, "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Temporal\nAnalyzer", "text_style": _shape_text_style(19),
    })
    scene.add({
        "type": "parallelogram", "name": "Question encoder", "x": 700, "y": 625, "w": 240, "h": 100,
        "slant": "right", "inset_px": 32,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Question\nEncoder", "text_style": _shape_text_style(18),
    })
    scene.arrow("Question to memory router", [[810, 625], [810, 585]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.arrow("Question to temporal analyzer", [[925, 675], [1065, 675], [1065, 585]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.arrow("Temporal analyzer to decoder", [[1160, 530], [1218, 530]], line=BLACK, line_width_px=3, head_length_px=15)
    scene.add({
        "type": "trapezoid", "name": "Answer and grounding decoder", "x": 1225, "y": 390, "w": 190, "h": 285,
        "orientation": "right_narrow", "inset_px": 42,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Answer &\nGrounding\nDecoder", "text_style": _shape_text_style(18),
    })
    scene.arrow("Decoder to answer card", [[1415, 465], [1462, 465]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.add({
        "type": "document", "name": "Natural language answer card", "x": 1468, "y": 385, "w": 118, "h": 165,
        "fill": WHITE, "line": BLACK, "line_width_px": 2,
        "text": "Natural-\nlanguage\nanswer\ncard", "text_style": _shape_text_style(14),
    })
    scene.arrow("Decoder to grounding bar", [[1415, 600], [1460, 600]], line=BLACK, line_width_px=3, head_length_px=14)
    scene.rect("Grounding bar frame", 1468, 575, 118, 58, fill=WHITE, line=BLACK, line_width_px=2)
    scene.add({"type": "polyline", "name": "Grounding bar axis", "points": [[1478, 610], [1576, 610]], "line": BLACK, "line_width_px": 1, "fill": "none"})
    for i, (x, w, fill) in enumerate([(1484, 18, LIGHT_GRAY), (1510, 20, PALE_RED), (1535, 28, PALE_GREEN)]):
        scene.rect(f"Grounding segment {i+1}", x, 588, w, 34, fill=fill, line="none")
    scene.rect("Grounding focus outline", 1532, 584, 34, 42, fill="none", line=GREEN, line_width_px=2)
    scene.text("Grounding label", 1455, 638, 145, 70, "temporal\ngrounding", text_style=_shape_text_style(15))
    scene.text("History label", 32, 690, 180, 35, "history clips", text_style=_shape_text_style(15))
    scene.text("Current label", 230, 690, 200, 35, "current clip", text_style=_shape_text_style(15))
    scene.arrow("Long memory update route", [[320, 465], [320, 345], [735, 345]], line=BLUE, line_width_px=2, dash=True, head_length_px=12)

    # Bottom panels.
    panel_y = 748
    panel_h = 240
    scene.roundrect("Feature calibration panel", 10, panel_y, 500, panel_h, radius_px=22, fill="none", line=BLUE, line_width_px=3, dash=True)
    scene.roundrect("Confidence routing panel", 520, panel_y, 535, panel_h, radius_px=22, fill="none", line=BLUE, line_width_px=3, dash=True)
    scene.roundrect("Outcome panel", 1065, panel_y, 525, panel_h, radius_px=22, fill="none", line=BLUE, line_width_px=3, dash=True)
    scene.text("Feature panel title", 70, 755, 380, 35, "Feature Calibration", text_style=_shape_text_style(19, bold=True))
    scene.text("Routing panel title", 580, 755, 420, 35, "Confidence-Guided Routing", text_style=_shape_text_style(19, bold=True))
    scene.text("Outcome panel title", 1130, 755, 390, 35, "Behavioral Outcome", text_style=_shape_text_style(19, bold=True))

    # Feature calibration subpanel.
    for i in range(4):
        scene.rect(f"Current feature cell {i+1}", 58 + i * 31, 830, 24, 24, fill=LIGHTER_BLUE, line=NAVY, line_width_px=1)
        scene.rect(f"Routed feature cell {i+1}", 58 + i * 31, 920, 24, 24, fill="#6E90BF", line=NAVY, line_width_px=1)
    scene.ellipse("Feature gap marker", 181, 849, 18, 18, fill=WHITE, line=NAVY, line_width_px=2)
    scene.arrow("Feature gap arrow", [[190, 895], [190, 864]], line=BLACK, line_width_px=2, head_length_px=9)
    scene.arrow("Routed gap arrow", [[190, 876], [190, 905]], line=BLACK, line_width_px=2, head_length_px=9)
    scene.add({
        "type": "trapezoid", "name": "Token encoder", "x": 230, "y": 825, "w": 105, "h": 125,
        "orientation": "right_narrow", "inset_px": 24,
        "fill": LIGHT_BLUE, "line": NAVY, "line_width_px": 3,
        "text": "Token\nEncoder", "text_style": _shape_text_style(16),
    })
    scene.arrow("Token encoder input", [[205, 887], [228, 887]], line=BLACK, line_width_px=2, head_length_px=10)
    scene.arrow("Token encoder output", [[338, 887], [377, 887]], line=BLACK, line_width_px=2, head_length_px=10)
    for i, color in enumerate(["#DF8E86", "#E69B93", "#E7B3A8", "#A3C18E", "#89B376", "#78A966"]):
        scene.rect(f"Calibrated feature cell {i+1}", 385, 822 + i * 24, 28, 24, fill=color, line=BLACK, line_width_px=1)
    scene.text("Current feature label", 28, 792, 185, 35, "current clip\nfeatures", text_style=_shape_text_style(13))
    scene.text("Memory feature label", 32, 946, 180, 35, "routed\nmemory features", text_style=_shape_text_style(13))
    scene.text("Gap label", 160, 865, 70, 32, "gap", text_style=_shape_text_style(12))
    scene.text("Drift label", 412, 842, 92, 94, "reduce\nsemantic\ndrift", text_style=_shape_text_style(12))

    # Confidence routing matrix and iterative bars.
    matrix_x, matrix_y = 625, 824
    rows, cols, cell = 5, 7, 28
    palette = ["#F0C9C5", "#D9E3F2", "#F1F2F4", "#D5DEEC", "#EBC0BC", "#E4E7EC"]
    for r in range(rows):
        scene.rect(f"Routing thumbnail border {r+1}", 555, matrix_y + r * cell, 58, cell, fill=WHITE, line=GRAY, line_width_px=1)
        scene.image(f"Routing thumbnail {r+1}", 557, matrix_y + 2 + r * cell, 54, cell - 4, f"media/abstract_frame_{r+2:02d}.png", grayscale=r != 2, alpha=0.72 if r != 2 else 1.0)
        for c in range(cols):
            color = palette[(r * 3 + c * 2) % len(palette)]
            scene.rect(f"Uncertainty score r{r+1}c{c+1}", matrix_x + c * cell, matrix_y + r * cell, cell, cell, fill=color, line=GRAY, line_width_px=1)
    scene.text("Matrix label", 585, 956, 250, 30, "uncertainty scores", text_style=_shape_text_style(13))
    bar_x = 855
    for i in range(6):
        scene.rect(f"Iterate one cell {i+1}", bar_x + i * 28, 824, 28, 26, fill="#EAB3AD" if i < 4 else "#F4DFDC", line=GRAY, line_width_px=1)
        scene.rect(f"Iterate two cell {i+1}", bar_x + i * 28, 933, 28, 26, fill="#A2C38A" if i < 3 else "#E1ECD9", line=GRAY, line_width_px=1)
    scene.text("Iterate one label", 845, 792, 185, 30, "Iterate I", text_style=_shape_text_style(15))
    scene.text("Noisy retrieval label", 842, 852, 205, 58, "broad noisy\nrouting", text_style=_shape_text_style(14))
    scene.text("Iterate two label", 845, 903, 185, 30, "Iterate II", text_style=_shape_text_style(15))
    scene.text("Focused pruning label", 830, 960, 225, 28, "after focused pruning", text_style=_shape_text_style(13))
    scene.arrow("Iteration loop down", [[1030, 840], [1044, 840], [1044, 935], [1027, 935]], line=BLACK, line_width_px=2, head_length_px=10)
    scene.arrow("Iteration loop up", [[842, 946], [824, 946], [824, 836], [842, 836]], line=BLACK, line_width_px=2, head_length_px=10)

    # Outcomes: three rows of before/after evidence bars.
    outcome_labels = [
        "(1) suppress irrelevant background",
        "(2) preserve key event boundaries",
        "(3) improve evidence grounding",
    ]
    for row, label in enumerate(outcome_labels):
        y = 810 + row * 62
        scene.text(f"Outcome label {row+1}", 1110, y - 18, 445, 28, label, text_style=_shape_text_style(11.5, align="left"))
        _add_prohibit(scene, f"Outcome prohibit {row+1}", 1082, y + 7, 26)
        # Before bar.
        scene.rect(f"Outcome before frame {row+1}", 1122, y + 4, 188, 34, fill=WHITE, line=GRAY, line_width_px=1)
        before_colors = [LIGHT_GRAY, "#C8CDD2", PALE_RED, "#AEB9C6", "#D3D6DA"]
        for i, color in enumerate(before_colors):
            scene.rect(f"Outcome before {row+1} segment {i+1}", 1124 + i * 36, y + 6, 34, 30, fill=color, line="none")
        scene.arrow(f"Outcome transition {row+1}", [[1312, y + 21], [1360, y + 21]], line=BLACK, line_width_px=2, head_length_px=11)
        scene.rect(f"Outcome after frame {row+1}", 1365, y + 4, 194, 34, fill=WHITE, line=GRAY, line_width_px=1)
        after_colors = [WHITE, WHITE, PALE_GREEN, WHITE, WHITE]
        focus_index = [1, 2, 3][row]
        for i, color in enumerate(after_colors):
            fill = PALE_GREEN if i == focus_index else color
            scene.rect(f"Outcome after {row+1} segment {i+1}", 1367 + i * 37, y + 6, 35, 30, fill=fill, line="none")
        scene.rect(f"Outcome focus outline {row+1}", 1365 + focus_index * 37, y + 2, 41, 38, fill="none", line=GREEN, line_width_px=2)

    scene_dict = {
        "version": "1.0",
        "document": {
            "title": "Synthetic event routing benchmark",
            "author": "OpenAI",
            "ppi": PPI,
            "created_utc": "2000-01-01T00:00:00Z",
            "deterministic_zip_timestamps": True,
        },
        "canvas": {"width_px": WIDTH, "height_px": HEIGHT, "background": WHITE},
        "reference_image": "synthetic_event_routing_reference.png",
        "include_reference_page": True,
        "reference_page_name": "Synthetic Reference",
        "pages": [
            {
                "name": "Editable Reconstruction",
                "background": WHITE,
                "shapes": scene.shapes,
            }
        ],
    }
    scene_path = work_dir / "synthetic_event_routing_scene.json"
    reference_path = work_dir / "synthetic_event_routing_reference.png"
    scene_path.write_text(json.dumps(scene_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    _render_scene(scene_dict, scene_path, reference_path)
    return scene_dict, scene_path, reference_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work" / "synthetic-event-routing")
    parser.add_argument("--output", type=Path, default=None, help="Output VSDX path. Defaults inside --work-dir.")
    parser.add_argument("--manifest", type=Path, default=None, help="Optional build manifest path.")
    args = parser.parse_args()

    work_dir = args.work_dir.resolve()
    output = (args.output or (work_dir / "synthetic_event_routing_editable.vsdx")).resolve()
    manifest = (args.manifest or (work_dir / "synthetic_event_routing_build_manifest.json")).resolve()
    _, scene_path, reference_path = build_scene(work_dir)
    result = build_scene_file(scene_path, output, manifest)
    print(json.dumps({
        "scene": str(scene_path),
        "reference": str(reference_path),
        "output": str(output),
        "manifest": str(manifest),
        "build": result,
    }, ensure_ascii=False, indent=2))
    return 0


def build_scene_file(scene_path: Path, output: Path, manifest: Path) -> dict[str, Any]:
    return build_vsdx_scene(scene_path, output, manifest)


if __name__ == "__main__":
    raise SystemExit(main())

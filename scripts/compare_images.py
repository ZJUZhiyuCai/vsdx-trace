#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "Pillow>=10,<12",
#   "numpy>=1.26,<3",
# ]
# ///
"""Compare a rendered reconstruction against its reference image.

The numeric score is a diagnostic prioritization aid, not a substitute for
human/model visual inspection. The script also writes an amplified difference
image and a 50/50 overlay for local correction.

Usage:
  python scripts/compare_images.py reference.png page-1.png --output-dir qa/diff
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageOps


def _load(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Image does not exist: {path}")
    image = Image.open(path)
    image.load()
    return image.convert("RGB")


def _resize_candidate(reference: Image.Image, candidate: Image.Image, mode: str) -> Image.Image:
    if candidate.size == reference.size:
        return candidate
    if mode == "resize":
        return candidate.resize(reference.size, Image.Resampling.LANCZOS)
    if mode == "contain":
        contained = ImageOps.contain(candidate, reference.size, Image.Resampling.LANCZOS)
        background = Image.new("RGB", reference.size, "white")
        x = (reference.width - contained.width) // 2
        y = (reference.height - contained.height) // 2
        background.paste(contained, (x, y))
        return background
    if mode == "cover":
        return ImageOps.fit(candidate, reference.size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    raise ValueError("mode must be resize, contain, or cover.")


def _gradient(gray: np.ndarray) -> np.ndarray:
    gx = np.zeros_like(gray, dtype=np.float32)
    gy = np.zeros_like(gray, dtype=np.float32)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) / 2.0
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) / 2.0
    return np.sqrt(gx * gx + gy * gy)


def _edge_f1(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref_gray = reference.mean(axis=2)
    cand_gray = candidate.mean(axis=2)
    ref_grad = _gradient(ref_gray)
    cand_grad = _gradient(cand_gray)
    ref_threshold = max(12.0, float(np.percentile(ref_grad, 83)))
    cand_threshold = max(12.0, float(np.percentile(cand_grad, 83)))
    ref_edges = ref_grad >= ref_threshold
    cand_edges = cand_grad >= cand_threshold
    # One-pixel tolerance by dilating each edge mask with eight neighbors.
    def dilate(mask: np.ndarray) -> np.ndarray:
        padded = np.pad(mask, 1, mode="constant", constant_values=False)
        output = np.zeros_like(mask)
        for dy in range(3):
            for dx in range(3):
                output |= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
        return output

    ref_dilated = dilate(ref_edges)
    cand_dilated = dilate(cand_edges)
    true_positive_precision = np.logical_and(cand_edges, ref_dilated).sum()
    true_positive_recall = np.logical_and(ref_edges, cand_dilated).sum()
    precision = true_positive_precision / max(1, cand_edges.sum())
    recall = true_positive_recall / max(1, ref_edges.sum())
    return float(2 * precision * recall / max(1e-9, precision + recall))


def _histogram_intersection(reference: np.ndarray, candidate: np.ndarray, bins: int = 32) -> float:
    scores: list[float] = []
    for channel in range(3):
        ref_hist, _ = np.histogram(reference[:, :, channel], bins=bins, range=(0, 256), density=False)
        cand_hist, _ = np.histogram(candidate[:, :, channel], bins=bins, range=(0, 256), density=False)
        ref_hist = ref_hist.astype(np.float64) / max(1, ref_hist.sum())
        cand_hist = cand_hist.astype(np.float64) / max(1, cand_hist.sum())
        scores.append(float(np.minimum(ref_hist, cand_hist).sum()))
    return float(sum(scores) / len(scores))


def compare(reference_path: Path, candidate_path: Path, output_dir: Path, mode: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reference = _load(reference_path)
    candidate_original = _load(candidate_path)
    candidate = _resize_candidate(reference, candidate_original, mode)
    aligned_path = output_dir / "candidate_aligned.png"
    candidate.save(aligned_path)

    reference_array = np.asarray(reference, dtype=np.float32)
    candidate_array = np.asarray(candidate, dtype=np.float32)
    absolute = np.abs(reference_array - candidate_array)
    mae = float(absolute.mean() / 255.0)
    rmse = float(math.sqrt(float((absolute**2).mean())) / 255.0)
    similarity_mae = max(0.0, 1.0 - mae)
    edge_similarity = _edge_f1(reference_array, candidate_array)
    histogram_similarity = _histogram_intersection(reference_array, candidate_array)
    diagnostic_score = 0.55 * similarity_mae + 0.30 * edge_similarity + 0.15 * histogram_similarity

    diff = ImageChops.difference(reference, candidate)
    diff = ImageOps.autocontrast(diff)
    diff = ImageEnhance.Contrast(diff).enhance(2.0)
    diff_path = output_dir / "difference_amplified.png"
    diff.save(diff_path)

    overlay = Image.blend(reference, candidate, 0.5)
    overlay_path = output_dir / "overlay_50_50.png"
    overlay.save(overlay_path)

    # Checkerboard alternation is effective for spotting global drift.
    checker = Image.new("RGB", reference.size)
    tile = max(20, round(min(reference.size) / 20))
    checker_pixels = checker.load()
    ref_pixels = reference.load()
    cand_pixels = candidate.load()
    for y in range(reference.height):
        for x in range(reference.width):
            checker_pixels[x, y] = ref_pixels[x, y] if ((x // tile) + (y // tile)) % 2 == 0 else cand_pixels[x, y]
    checker_path = output_dir / "checkerboard.png"
    checker.save(checker_path)

    report = {
        "reference": str(reference_path),
        "candidate": str(candidate_path),
        "reference_size": list(reference.size),
        "candidate_original_size": list(candidate_original.size),
        "alignment_mode": mode,
        "metrics": {
            "normalized_mae": round(mae, 6),
            "normalized_rmse": round(rmse, 6),
            "pixel_similarity_1_minus_mae": round(similarity_mae, 6),
            "edge_f1_with_1px_tolerance": round(edge_similarity, 6),
            "rgb_histogram_intersection": round(histogram_similarity, 6),
            "diagnostic_score": round(diagnostic_score, 6),
        },
        "interpretation": (
            "Use the score only to rank iterations. Inspect the overlay, checkerboard, and amplified difference before shipping. "
            "Text antialiasing and font substitution can lower the score even when geometry is acceptable."
        ),
        "artifacts": {
            "aligned_candidate": str(aligned_path),
            "difference": str(diff_path),
            "overlay": str(overlay_path),
            "checkerboard": str(checker_path),
        },
    }
    report_path = output_dir / "metrics.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**report, "report": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mode", choices=("resize", "contain", "cover"), default="resize")
    args = parser.parse_args()
    try:
        report = compare(
            args.reference.expanduser().resolve(),
            args.candidate.expanduser().resolve(),
            args.output_dir.expanduser().resolve(),
            args.mode,
        )
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

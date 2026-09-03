#!/usr/bin/env python3
"""Scan a Skill directory or archive for common privacy leaks.

Checks plaintext and nested VSDX/ZIP XML for email addresses, absolute local
paths, conversation/file identifiers, UUID-like identifiers, and caller-supplied
deny terms. It also reports image EXIF/text metadata and archive timestamps.
The scanner is conservative: a clean result reduces obvious leakage risk but is
not a proof of anonymization.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".py", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".xml", ".rels", ".csv", ".svg", ".html", ".css", ".js",
}
ARCHIVE_SUFFIXES = {".vsdx", ".vstx", ".vssx", ".vsdm", ".zip", ".skill"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
FIXED_TIMES = {(1980, 1, 1, 0, 0, 0), (2000, 1, 1, 0, 0, 0)}


def _patterns() -> dict[str, re.Pattern[str]]:
    local_roots = "(?:" + "|".join(("mnt", "home", "Users", "private/tmp", "var/folders")) + ")"
    return {
        "email": re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "absolute_posix_path": re.compile(r"(?<![\w:])/" + local_roots + r"/(?:[^\s\"'<>]|\\ )+"),
        "absolute_windows_user_path": re.compile(r"\b[A-Za-z]:\\(?:Users|Documents and Settings)\\[^\s\"'<>]+", re.I),
        "conversation_file_id": re.compile(r"\bfile_[0-9a-f]{16,}\b", re.I),
        "mounted_user_id": re.compile(r"\buser-[A-Za-z0-9]{16,}\b"),
        "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I),
    }


def _decode_text(data: bytes) -> str | None:
    if b"\x00" in data[:4096]:
        return None
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _scan_text(label: str, text: str, deny_terms: list[str], findings: list[dict[str, Any]]) -> None:
    for category, pattern in _patterns().items():
        for match in pattern.finditer(text):
            findings.append({
                "category": category,
                "location": label,
                "line": text.count("\n", 0, match.start()) + 1,
            })
    folded = text.casefold()
    for term in deny_terms:
        if not term:
            continue
        term_folded = term.casefold()
        start = 0
        while True:
            index = folded.find(term_folded, start)
            if index < 0:
                break
            findings.append({
                "category": "deny_term",
                "location": label,
                "line": text.count("\n", 0, index) + 1,
                "term_sha256_12": hashlib.sha256(term.encode("utf-8")).hexdigest()[:12],
            })
            start = index + max(1, len(term_folded))


def _scan_archive(path: Path, label: str, deny_terms: list[str], findings: list[dict[str, Any]], archive_report: list[dict[str, Any]]) -> None:
    timestamps: set[tuple[int, int, int, int, int, int]] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            for info in infos:
                timestamps.add(info.date_time)
                _scan_text(f"{label}!/{info.filename}", info.filename, deny_terms, findings)
                if Path(info.filename).suffix.lower() in TEXT_SUFFIXES:
                    text = _decode_text(archive.read(info))
                    if text is not None:
                        _scan_text(f"{label}!/{info.filename}", text, deny_terms, findings)
    except (OSError, zipfile.BadZipFile) as exc:
        findings.append({"category": "unreadable_archive", "location": label, "detail": str(exc)})
        return
    archive_report.append({
        "path": label,
        "entry_count": len(infos),
        "timestamps": [list(item) for item in sorted(timestamps)],
        "all_timestamps_neutral": bool(timestamps) and timestamps.issubset(FIXED_TIMES),
    })


def _scan_image(path: Path, label: str, findings: list[dict[str, Any]], image_report: list[dict[str, Any]]) -> None:
    if Image is None:
        image_report.append({"path": label, "status": "Pillow unavailable"})
        return
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            suspicious_keys = [
                key for key in image.info
                if str(key).lower() in {"author", "comment", "description", "software", "date", "datetime", "xml", "xmp"}
            ]
            if len(exif) > 0:
                findings.append({"category": "image_exif", "location": label, "entries": len(exif)})
            if suspicious_keys:
                findings.append({"category": "image_text_metadata", "location": label, "keys": suspicious_keys})
            image_report.append({
                "path": label,
                "size": list(image.size),
                "mode": image.mode,
                "exif_entries": len(exif),
                "suspicious_metadata_keys": suspicious_keys,
            })
    except OSError as exc:
        findings.append({"category": "unreadable_image", "location": label, "detail": str(exc)})


def scan(root: Path, deny_terms: list[str]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    archives: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    files_scanned = 0

    if root.is_file():
        candidates: Iterable[Path] = [root]
        base = root.parent
    else:
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
        base = root

    for path in candidates:
        files_scanned += 1
        relative = path.relative_to(base).as_posix() if path != root else path.name
        _scan_text(relative, relative, deny_terms, findings)
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            text = _decode_text(path.read_bytes())
            if text is not None:
                _scan_text(relative, text, deny_terms, findings)
        elif suffix in ARCHIVE_SUFFIXES:
            _scan_archive(path, relative, deny_terms, findings, archives)
        elif suffix in IMAGE_SUFFIXES:
            _scan_image(path, relative, findings, images)

    return {
        "root": root.name,
        "files_scanned": files_scanned,
        "deny_term_count": len([term for term in deny_terms if term]),
        "clean": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "archives": archives,
        "images": images,
        "limitations": [
            "Pattern scanning cannot prove that visual content is anonymous.",
            "A renamed or lightly edited private image remains private; replace it with synthetic or explicitly licensed content.",
            "Review domain-specific identifiers and proprietary wording manually before distribution.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--deny-term", action="append", default=[], help="Exact sensitive term to reject; may be repeated.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan(args.path.resolve(), args.deny_term)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

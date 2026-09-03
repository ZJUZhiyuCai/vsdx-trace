#!/usr/bin/env python3
"""Render a VSDX to PDF and page PNGs using LibreOffice and Poppler.

This is a compatibility/visual-QA renderer, not the source of truth. Microsoft
Visio can render text slightly differently because of font substitution.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VSDX via LibreOffice")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dpi", type=int, default=100)
    parser.add_argument("--first-page-only", action="store_true")
    args = parser.parse_args()

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice:
        print("ERROR: LibreOffice/soffice is not installed", file=sys.stderr)
        return 2
    if not pdftoppm:
        print("ERROR: pdftoppm (Poppler) is not installed", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vsdx-render-") as td:
        tmp = Path(td)
        profile = tmp / "lo-profile"
        profile.mkdir()
        run([
            soffice,
            "--headless",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "pdf",
            "--outdir", str(tmp),
            str(args.input.resolve()),
        ])
        pdf = tmp / (args.input.stem + ".pdf")
        if not pdf.exists():
            pdfs = list(tmp.glob("*.pdf"))
            if not pdfs:
                raise RuntimeError("LibreOffice did not create a PDF")
            pdf = pdfs[0]
        final_pdf = args.output_dir / pdf.name
        shutil.copy2(pdf, final_pdf)
        prefix = args.output_dir / args.input.stem
        cmd = [pdftoppm, "-png", "-r", str(args.dpi)]
        if args.first_page_only:
            cmd += ["-f", "1", "-l", "1", "-singlefile"]
        cmd += [str(final_pdf), str(prefix)]
        run(cmd)
    pngs = sorted(str(p) for p in args.output_dir.glob(args.input.stem + "*.png"))
    print(json.dumps({"pdf": str(final_pdf), "pngs": pngs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

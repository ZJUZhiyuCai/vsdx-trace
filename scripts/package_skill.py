#!/usr/bin/env python3
"""Package VSDX Trace into deterministic Core and privacy-sanitized Full ZIPs.

Core omits the synthetic Gold Standard and its exact example script. Full keeps
all generic tooling plus the procedurally generated Gold Standard. Neither
edition includes user task materials, caches, local work directories, or build
logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

EXCLUDE_ALWAYS = {
    ".DS_Store",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "PACKAGE_MANIFEST.json",
    "pyproject.toml",
    "requirements-dev.txt",
}
EXCLUDE_PARTS = {
    "__pycache__",
    ".git",
    ".github",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "docs",
    "tests",
    "work",
}
CORE_EXCLUDE_FILES = {
    "examples/synthetic_event_routing_case.py",
    "references/GOLD_STANDARD.md",
    "SKILL_TEST_REPORT.json",
}


def include_path(relative: str, edition: str) -> bool:
    parts = set(Path(relative).parts)
    if parts & EXCLUDE_PARTS:
        return False
    if Path(relative).name in EXCLUDE_ALWAYS or relative.endswith((".pyc", ".pyo")):
        return False
    if edition == "core":
        if relative.startswith("assets/gold/") or relative in CORE_EXCLUDE_FILES:
            return False
    return True


def transform_text(relative: str, data: bytes, edition: str) -> bytes:
    if edition != "core" or relative not in {
        "README.md",
        "README.zh-CN.md",
        "SKILL.md",
        "examples/README.md",
    }:
        return data
    text = data.decode("utf-8")
    if relative in {"README.md", "README.zh-CN.md"}:
        text = re.sub(
            r"\n<!-- full-only:start -->.*?<!-- full-only:end -->\n",
            "\n",
            text,
            flags=re.S,
        )
    elif relative == "SKILL.md":
        text = re.sub(
            r"## Gold Standard\n.*?(?=\n## 失败模式)",
            "## Gold Standard\n\nCore 版不含合成 Gold Standard 资产；通用工作流、场景生成器、验证器和 QA 工具保持完整。\n",
            text,
            flags=re.S,
        )
        text = text.replace("- [Gold Standard 说明](references/GOLD_STANDARD.md)\n", "")
    elif relative == "examples/README.md":
        text = re.sub(r"\n## Privacy-safe full reconstruction case\n.*", "\n", text, flags=re.S)
    return text.encode("utf-8")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def package(root: Path, output: Path, edition: str) -> dict:
    root = root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = root.name
    entries: list[dict[str, object]] = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(root.rglob("*")):
            if not source.is_file() or source.resolve() == output.resolve():
                continue
            relative = source.relative_to(root).as_posix()
            if not include_path(relative, edition):
                continue
            data = transform_text(relative, source.read_bytes(), edition)
            archive_name = f"{prefix}/{relative}"
            archive.writestr(_zip_info(archive_name), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            entries.append({
                "path": relative,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        manifest = {
            "skill": prefix,
            "edition": "privacy-sanitized-full" if edition == "full" else "core",
            "version": (root / "VERSION").read_text(encoding="utf-8").strip(),
            "deterministic_archive_timestamps": True,
            "files": entries,
        }
        manifest_data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        archive.writestr(
            _zip_info(f"{prefix}/PACKAGE_MANIFEST.json"),
            manifest_data,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )
    data = output.read_bytes()
    return {
        "output": output.name,
        "edition": manifest["edition"],
        "files": len(entries) + 1,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--edition", choices=("core", "full", "both"), default="both")
    args = parser.parse_args()
    editions = ("core", "full") if args.edition == "both" else (args.edition,)
    reports = []
    for edition in editions:
        filename = (
            "vsdx-trace.skill.zip"
            if edition == "core"
            else "vsdx-trace-privacy-sanitized-full.skill.zip"
        )
        reports.append(package(args.root, args.output_dir / filename, edition))
    print(json.dumps({"packages": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

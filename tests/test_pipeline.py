from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from package_skill import package  # noqa: E402
from validate_vsdx import validate  # noqa: E402
from vsdx_builder import build_scene  # noqa: E402


def test_skill_metadata_is_consistent() -> None:
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = skill_text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    interface = yaml.safe_load((ROOT / "agents/openai.yaml").read_text(encoding="utf-8"))

    assert metadata["name"] == "vsdx-trace"
    assert metadata["metadata"]["version"] == (ROOT / "VERSION").read_text().strip()
    assert "$vsdx-trace" in interface["interface"]["default_prompt"]


def test_template_builds_and_validates(tmp_path: Path) -> None:
    output = tmp_path / "template.vsdx"
    manifest_path = tmp_path / "template.manifest.json"
    manifest = build_scene(ROOT / "assets/templates/scene-template.json", output, manifest_path)
    report = validate(output)

    assert report["valid"] is True
    assert report["issues"] == []
    assert manifest["pages"][0]["shape_count"] == 15
    assert manifest["pages"][0]["image_count"] == 1


def test_bundled_gold_standard_is_valid() -> None:
    report = validate(ROOT / "assets/gold/synthetic_event_routing_editable.vsdx")

    assert report["valid"] is True
    assert report["issues"] == []
    assert report["pages"][0]["shape_count"] == 269
    assert report["pages"][0]["text_shape_count"] == 54
    assert report["pages"][0]["embedded_image_count"] == 19


def test_full_package_is_deterministic_and_manifested(tmp_path: Path) -> None:
    first = tmp_path / "first.skill.zip"
    second = tmp_path / "second.skill.zip"
    package(ROOT, first, "full")
    package(ROOT, second, "full")

    assert first.read_bytes() == second.read_bytes()

    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        prefix = "vsdx-trace/"
        manifest = json.loads(archive.read(prefix + "PACKAGE_MANIFEST.json"))
        assert manifest["skill"] == "vsdx-trace"
        assert manifest["version"] == (ROOT / "VERSION").read_text().strip()
        assert manifest["content_scope"] == "generated-package"
        assert manifest["repository_only_content_excluded"] is True
        assert not any("__pycache__" in name or "/.git/" in name for name in names)
        assert not any("/assets/marketing/" in name for name in names)
        for item in manifest["files"]:
            data = archive.read(prefix + item["path"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"]

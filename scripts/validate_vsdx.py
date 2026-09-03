#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "lxml>=5,<7",
# ]
# ///
"""Perform structural validation of a generated VSDX package.

Checks the OPC package, required Visio parts, XML well-formedness, page
relationships, numeric/unique shape IDs, and embedded-image relationships.
This is a structural gate; it does not replace opening the file in desktop
Microsoft Visio or visual render review.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

VISIO_NS = "http://schemas.microsoft.com/office/visio/2012/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"v": VISIO_NS, "r": REL_NS, "pr": PKG_REL_NS, "ct": CT_NS}


def _parse_xml(archive: zipfile.ZipFile, path: str, issues: list[str]) -> etree._Element | None:
    try:
        data = archive.read(path)
    except KeyError:
        issues.append(f"Missing required part: {path}")
        return None
    try:
        return etree.fromstring(data)
    except etree.XMLSyntaxError as error:
        issues.append(f"Malformed XML in {path}: {error}")
        return None


def _resolve(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def validate(path: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    page_summaries: list[dict[str, Any]] = []
    if not path.is_file():
        return {"valid": False, "issues": [f"File does not exist: {path}"], "warnings": [], "pages": []}
    try:
        archive = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as error:
        return {"valid": False, "issues": [f"Not a valid ZIP/OPC package: {error}"], "warnings": [], "pages": []}

    with archive:
        names = set(archive.namelist())
        required = {
            "[Content_Types].xml",
            "_rels/.rels",
            "visio/document.xml",
            "visio/_rels/document.xml.rels",
            "visio/windows.xml",
            "visio/pages/pages.xml",
            "visio/pages/_rels/pages.xml.rels",
        }
        for missing in sorted(required - names):
            issues.append(f"Missing required part: {missing}")

        content_types = _parse_xml(archive, "[Content_Types].xml", issues)
        if content_types is not None:
            overrides = {
                node.get("PartName"): node.get("ContentType")
                for node in content_types.xpath("./ct:Override", namespaces=NS)
            }
            expected_overrides = {
                "/visio/document.xml": "application/vnd.ms-visio.drawing.main+xml",
                "/visio/pages/pages.xml": "application/vnd.ms-visio.pages+xml",
                "/visio/windows.xml": "application/vnd.ms-visio.windows+xml",
            }
            for part_name, content_type in expected_overrides.items():
                if overrides.get(part_name) != content_type:
                    issues.append(f"Incorrect or missing content type for {part_name}: expected {content_type}.")

        _parse_xml(archive, "visio/document.xml", issues)
        _parse_xml(archive, "visio/windows.xml", issues)
        root_rels = _parse_xml(archive, "_rels/.rels", issues)
        if root_rels is not None:
            document_targets = [
                relationship.get("Target")
                for relationship in root_rels.xpath("./pr:Relationship", namespaces=NS)
                if relationship.get("Type") == "http://schemas.microsoft.com/visio/2010/relationships/document"
            ]
            if "visio/document.xml" not in document_targets and "/visio/document.xml" not in document_targets:
                issues.append("Root relationships do not target visio/document.xml with the Visio document relationship type.")

        pages_root = _parse_xml(archive, "visio/pages/pages.xml", issues)
        pages_rels_root = _parse_xml(archive, "visio/pages/_rels/pages.xml.rels", issues)
        page_relationships: dict[str, str] = {}
        if pages_rels_root is not None:
            for relationship in pages_rels_root.xpath("./pr:Relationship", namespaces=NS):
                relationship_id = relationship.get("Id")
                target = relationship.get("Target")
                if relationship_id and target:
                    page_relationships[relationship_id] = _resolve("visio/pages/pages.xml", target)

        if pages_root is not None:
            page_nodes = pages_root.xpath("./v:Page", namespaces=NS)
            if not page_nodes:
                issues.append("pages.xml contains no Page element.")
            seen_page_ids: set[str] = set()
            for page_index, page_node in enumerate(page_nodes, start=1):
                page_id = page_node.get("ID")
                page_name = page_node.get("NameU") or page_node.get("Name") or f"Page-{page_index}"
                if page_id is None or not page_id.isdigit():
                    issues.append(f"Page {page_name!r} has a non-numeric ID: {page_id!r}.")
                elif page_id in seen_page_ids:
                    issues.append(f"Duplicate Page ID {page_id}.")
                else:
                    seen_page_ids.add(page_id)
                rel_nodes = page_node.xpath("./v:Rel", namespaces=NS)
                if not rel_nodes:
                    issues.append(f"Page {page_name!r} has no Rel child.")
                    continue
                relationship_id = rel_nodes[0].get(f"{{{REL_NS}}}id")
                if not relationship_id or relationship_id not in page_relationships:
                    issues.append(f"Page {page_name!r} references missing relationship {relationship_id!r}.")
                    continue
                page_part = page_relationships[relationship_id]
                page_root = _parse_xml(archive, page_part, issues)
                if page_root is None:
                    continue
                if page_root.tag != f"{{{VISIO_NS}}}PageContents":
                    issues.append(f"{page_part} root is not PageContents.")
                shape_nodes = page_root.xpath(".//v:Shape", namespaces=NS)
                shape_ids: set[str] = set()
                foreign_count = 0
                text_count = 0
                page_rels_path = posixpath.join(posixpath.dirname(page_part), "_rels", posixpath.basename(page_part) + ".rels")
                page_relations: dict[str, str] = {}
                if page_rels_path in names:
                    page_rels = _parse_xml(archive, page_rels_path, issues)
                    if page_rels is not None:
                        for relationship in page_rels.xpath("./pr:Relationship", namespaces=NS):
                            relationship_id_local = relationship.get("Id")
                            target = relationship.get("Target")
                            if relationship_id_local and target:
                                page_relations[relationship_id_local] = _resolve(page_part, target)
                for shape_node in shape_nodes:
                    shape_id = shape_node.get("ID")
                    if shape_id is None or not shape_id.isdigit():
                        issues.append(f"{page_part}: shape has non-numeric ID {shape_id!r}.")
                    elif shape_id in shape_ids:
                        issues.append(f"{page_part}: duplicate shape ID {shape_id}.")
                    else:
                        shape_ids.add(shape_id)
                    if shape_node.xpath("./v:Text", namespaces=NS):
                        text_count += 1
                    foreign_data = shape_node.xpath("./v:ForeignData", namespaces=NS)
                    if foreign_data:
                        foreign_count += 1
                        rel_nodes_local = foreign_data[0].xpath("./v:Rel", namespaces=NS)
                        if not rel_nodes_local:
                            issues.append(f"{page_part}: foreign shape {shape_id} has no ForeignData/Rel child.")
                        else:
                            image_rel_id = rel_nodes_local[0].get(f"{{{REL_NS}}}id")
                            if not image_rel_id or image_rel_id not in page_relations:
                                issues.append(f"{page_part}: foreign shape {shape_id} references missing image relationship {image_rel_id!r}.")
                            else:
                                target_part = page_relations[image_rel_id]
                                if target_part not in names:
                                    issues.append(f"{page_part}: embedded image target is missing: {target_part}.")
                if not shape_nodes:
                    warnings.append(f"Page {page_name!r} has no shapes.")
                page_summaries.append(
                    {
                        "name": page_name,
                        "part": page_part,
                        "shape_count": len(shape_nodes),
                        "text_shape_count": text_count,
                        "embedded_image_count": foreign_count,
                    }
                )

        # Warn about an entire-page bitmap-only reconstruction: valid VSDX, poor editability.
        if page_summaries:
            first = page_summaries[0]
            if first["shape_count"] == 1 and first["embedded_image_count"] == 1:
                warnings.append("The first page contains only one embedded bitmap; this is not a genuinely editable reconstruction.")

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "pages": page_summaries,
        "file": str(path),
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsdx", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    report = validate(args.vsdx.expanduser().resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.expanduser().resolve().write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

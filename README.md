# High-Fidelity Visio Reconstruction Skill

![CI](https://github.com/ZJUZhiyuCai/high-fidelity-visio-reconstruction/actions/workflows/ci.yml/badge.svg)

Reconstruct screenshots, scientific figures, system diagrams, flowcharts, and architecture graphics as high-fidelity, independently editable Microsoft Visio `.vsdx` files.

把截图、论文插图、系统图、流程图和模型架构图高保真复刻成逐元素可编辑的 Microsoft Visio `.vsdx` 文件。

![Synthetic Event Routing benchmark](assets/gold/synthetic_event_routing_preview.png)

## Highlights

- Native editable text, panels, arrows, nodes, tokens, timelines, and diagram primitives.
- Raster fragments are limited to content that is not reasonably vectorizable, such as photographs, microscopy, heatmaps, or dense evidence strips.
- Pixel-coordinate scene format with fixed VSDX metadata and archive timestamps for reproducible builds.
- Structural validation, headless rendering, overlays, checkerboards, and image-difference metrics.
- A fully synthetic, reproducible Gold Standard with no user-provided source material.
- A separate reference page for calibration without using the full reference image as the editable page background.

## Install in Codex

```bash
git clone https://github.com/ZJUZhiyuCai/high-fidelity-visio-reconstruction.git \
  ~/.codex/skills/high-fidelity-visio-reconstruction
```

The skill becomes discoverable on the next Codex turn. Other Agent Skills-compatible clients can install the repository as a skill folder containing `SKILL.md`.

## Use

Upload a clear reference image and ask:

> Reconstruct this image as a high-fidelity, editable Visio file.

或：

> 把这张图高保真复刻成可编辑的 Visio 文件。

The default deliverables are an editable `.vsdx`, a first-page PNG preview, and a structural validation report. The generated VSDX includes an editable reconstruction page and, when requested, a separate original-reference page.

## Requirements

- Python 3.10+
- Pillow 10+
- NumPy 1.26+
- lxml 5–6
- Optional: LibreOffice and Poppler for headless rendering QA

Microsoft Visio is not required to construct the VSDX.

```bash
python -m pip install -r requirements.txt
```

## Quick validation

```bash
mkdir -p work
python scripts/build_from_scene.py \
  assets/templates/scene-template.json \
  work/scene-template-output.vsdx \
  --manifest work/scene-template-output.manifest.json

python scripts/validate_vsdx.py work/scene-template-output.vsdx
```

With LibreOffice and Poppler installed:

```bash
python scripts/render_vsdx.py \
  work/scene-template-output.vsdx work/rendered \
  --dpi 100 --first-page-only
```

## Repository layout

- `SKILL.md` — routing, workflow, privacy boundaries, and delivery requirements
- `scripts/` — VSDX generation, validation, rendering, image comparison, crop extraction, and scene inspection
- `references/` — reconstruction playbook, scene schema, OOXML notes, quality rubric, and troubleshooting
- `assets/templates/` — reusable scene template and synthetic sample image
- `assets/gold/` — synthetic reference, editable VSDX, preview, validation, and quality data
- `examples/synthetic_event_routing_case.py` — deterministic end-to-end benchmark generator
- `evals/evals.json` — behavioral evaluation prompts
- `PRIVACY_AUDIT.json` — sanitization and privacy review record

## Verified baseline

- Generic template: valid VSDX with 15 shapes, 6 text shapes, and 1 local bitmap.
- Synthetic Gold Standard: 269 editable main-page shapes, including 54 text shapes and 19 local bitmaps, plus a synthetic reference page.
- Recorded visual QA: approximately `0.9485` pixel similarity, `0.8388` edge F1, and `0.9171` diagnostic score.

Rendering can vary with font substitution and antialiasing. Do not claim Microsoft Visio desktop validation unless the file has actually been tested there.

Across Pillow or zlib versions, lossless PNG compression bytes may differ even when decoded pixels, VSDX XML, relationships, metadata, and timestamps are identical.

## Privacy

Real user references, crops, coordinates, local paths, names, organizations, chat identifiers, and build logs must not be copied into reusable examples or public releases. The bundled benchmark is generated programmatically and contains no user-provided reference image.

Run the included scanner before publishing modified packages:

```bash
python scripts/privacy_scan.py .
```

## License

MIT. See [LICENSE](LICENSE).

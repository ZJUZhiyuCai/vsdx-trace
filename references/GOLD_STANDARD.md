# Gold Standard: Synthetic Event Routing Benchmark

## Purpose

This worked example exercises the full reconstruction pipeline without carrying
forward any user material. The reference image, local raster frames, labels,
scene JSON, and VSDX are generated deterministically by
`examples/synthetic_event_routing_case.py`.

VSDX XML, relationships, metadata, timestamps, and decoded image pixels are
reproducible. Lossless PNG byte streams may differ across Pillow/zlib versions
while decoding to identical pixels.

It intentionally contains no personal name, organization, paper or framework
title, logo, watermark, author list, email address, chat identifier, local build
path, real photograph, or user-uploaded asset.

## What the example demonstrates

- a 1600 x 1000 px source canvas mapped at 100 px/in
- two pages: editable reconstruction and synthetic reference
- 269 independently selectable shapes on the main page
- 54 editable text shapes
- 19 local bitmap shapes made from procedurally generated abstract frames
- dashed rounded panels, custom arrows, cylinders, trapezoids, a document card,
  a matrix, warning icons, feature bars, and temporal-grounding elements
- deterministic VSDX metadata and ZIP entry timestamps

The validation report is
`assets/gold/synthetic_event_routing_validation.json`, the scene is
`assets/gold/synthetic_event_routing_scene.json`, and visual diagnostics are in
`assets/gold/synthetic_event_routing_quality_metrics.json`.

## Key lessons

1. Use direct VSDX package generation instead of a conversion chain that may
   flatten or reinterpret shapes.
2. Keep source-image pixels as the single coordinate truth and convert to Visio
   inches only during serialization.
3. Split mixed-format phrases into adjacent text shapes.
4. Use separate arrow shafts and heads for renderer stability.
5. Keep only genuinely raster-like evidence as local image shapes.
6. Include a separate reference page for calibration, never as the editable
   page's full-image background.
7. Validate the OPC structure, render headlessly, and inspect overlays and
   differences before delivery.
8. For reusable packages, replace task-specific examples with synthetic assets
   and scrub metadata, absolute paths, archive timestamps, and identifiers.

## Inspect the bundled result

```bash
python scripts/validate_vsdx.py \
  assets/gold/synthetic_event_routing_editable.vsdx
python scripts/extract_vsdx_scene.py \
  assets/gold/synthetic_event_routing_editable.vsdx \
  work/synthetic-inventory.json --ppi 100
```

## Rebuild from zero

```bash
python examples/synthetic_event_routing_case.py \
  --work-dir work/synthetic-event-routing \
  --output work/synthetic-event-routing/synthetic_event_routing_editable.vsdx
```

Then run the standard validation, render, and comparison commands against the
generated reference.

## Measured QA baseline

In the recorded LibreOffice/Poppler environment:

- pixel similarity: approximately 0.9485
- edge F1 with 1 px tolerance: approximately 0.8388
- diagnostic score: approximately 0.9171

These are iteration diagnostics, not universal acceptance thresholds. Font
substitution and antialiasing vary by machine; semantic editability and visual
inspection remain decisive.

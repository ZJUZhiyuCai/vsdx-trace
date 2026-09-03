# Scene JSON Schema

The bundled generator consumes a JSON document in source-image pixel coordinates.

## Top-level fields

```json
{
  "version": "1.0",
  "document": {
    "title": "Document title",
    "author": "Author",
    "ppi": 100,
    "created_utc": "2000-01-01T00:00:00Z",
    "deterministic_zip_timestamps": true
  },
  "canvas": {
    "width_px": 2048,
    "height_px": 1529,
    "background": "#FFFFFF"
  },
  "reference_image": "reference.png",
  "include_reference_page": true,
  "reference_page_name": "Original Reference",
  "pages": []
}
```

`reference_image` is resolved relative to the scene JSON. When `include_reference_page` is true, the generator adds a full-raster comparison page.

`document.created_utc` is optional. When present, it is written to VSDX core properties instead of the current clock time. `document.deterministic_zip_timestamps` fixes all internal VSDX ZIP entry timestamps to a neutral value. Use both for synthetic examples, regression fixtures, and shareable packages; do not use them to disguise the provenance of real evidence.

For privacy-safe distribution, keep user references outside the reusable Skill tree. Package only generic templates or procedurally generated examples, and scan generated manifests for absolute paths before sharing.

## Page

```json
{
  "name": "Editable Reconstruction",
  "width_px": 2048,
  "height_px": 1529,
  "ppi": 100,
  "background": "#FFFFFF",
  "shapes": []
}
```

Page dimensions default to the top-level canvas.

## Common shape fields

```json
{
  "type": "roundrect",
  "name": "Memory Router",
  "x": 850,
  "y": 650,
  "w": 240,
  "h": 140,
  "fill": "#CFDCF0",
  "line": "#17335D",
  "line_width_px": 4,
  "dash": false,
  "angle_deg": 0,
  "text": "Memory\nRouter",
  "text_style": {
    "font_family": "Arial",
    "size_pt": 27,
    "bold": false,
    "italic": false,
    "underline": false,
    "color": "#000000",
    "align": "center",
    "valign": "middle",
    "margin_px": 1.5
  }
}
```

Accepted aliases include `width`/`height`, `stroke`, `stroke_width_px`, `font_size_pt` and `text_color`.

## Supported types

### `rect`

Axis-aligned rectangle.

### `roundrect`

Rounded rectangle. Additional fields:

```json
{"radius_px": 24, "corner_segments": 6}
```

### `ellipse`

Ellipse or circle. Additional field `segments` controls polygon approximation.

### `text`

Transparent text box. Requires `x, y, w, h, text`.

### `polygon`

Closed shape using absolute source-pixel coordinates:

```json
{
  "type": "polygon",
  "points": [[100,100],[200,120],[180,220],[90,200]],
  "fill": "#FFFFFF",
  "line": "#000000"
}
```

### `polyline` or `line`

Open path. Use absolute points and no fill.

### `arrow`

Polyline with an independently editable triangular head:

```json
{
  "type": "arrow",
  "points": [[200,300],[420,300],[420,500]],
  "line": "#000000",
  "line_width_px": 3,
  "head_length_px": 15,
  "head_width_px": 14,
  "end_head": true,
  "start_head": false
}
```

`double_arrow` or `start_head: true` adds a start head.

### `cylinder`

Database/memory-bank body. Additional fields:

```json
{"ellipse_height_px": 35, "segments": 18}
```

The generator expands this into an outer body and a top ellipse outline.

### `document`

Document/answer-card with a wavy bottom. Additional fields:

```json
{"wave_height_px": 24, "wave_cycles": 1.25, "wave_samples": 24}
```

### `trapezoid`

Additional fields:

```json
{"orientation": "right_narrow", "inset_px": 40}
```

Supported orientations: `top_narrow`, `bottom_narrow`, `left_narrow`, `right_narrow`.

### `parallelogram`

Additional fields: `slant: right|left`, `inset_px`.

### `triangle` and `diamond`

Semantic convenience primitives.

### `image`

```json
{
  "type": "image",
  "name": "Current clip",
  "x": 340,
  "y": 520,
  "w": 220,
  "h": 150,
  "path": "reference.png",
  "crop": [310, 480, 220, 150],
  "alpha": 1.0,
  "grayscale": false
}
```

`crop` is `[x, y, width, height]`. `crop_box` may instead be `[left, top, right, bottom]`.

## Z-order

Shapes are written in list order. Earlier shapes are behind later shapes. Expand compound elements such as borders and labels in the intended stacking order.

## Mixed-style text

The current scene format applies one text style per shape. Split mixed-style text into adjacent text shapes.

# Detailed Reconstruction Playbook

## 1. Objective function

Treat the task as a constrained reconstruction problem with three simultaneous objectives:

1. **Visual fidelity**: global composition, local geometry, text placement, color and line style.
2. **Editability**: native text and vector shapes whenever feasible.
3. **Package reliability**: a structurally valid VSDX that opens in compatible software.

Do not maximize one objective by destroying the others. A full-page screenshot scores highly on pixel similarity but fails editability; an abstract redraw is editable but fails fidelity.

## 2. Build a scene inventory

Create a table or JSON list with these fields:

- semantic name
- primitive type
- x, y, width, height in source pixels
- z-order
- fill and stroke color
- stroke width and dash style
- text, font size, weight, alignment, color
- vector/raster decision
- crop box for raster fragments
- confidence and open questions

For a dense figure, segment the inventory by panels rather than keeping one flat list.

## 3. Decomposition order

### Pass A: global scaffold

- page background
- large rounded container(s)
- major headings
- major dashed panels

### Pass B: central information flow

- source clip stacks
- encoders/routers/reasoners/decoders
- memory banks
- main arrows and branch lines

### Pass C: subpanels

- calibration panel
- uncertainty matrix panel
- outcome panel

### Pass D: text and annotations

- titles and labels
- formula fragments
- red failure annotations
- explanatory captions

### Pass E: micro-elements

- warning triangles
- prohibition marks
- tokens and matrix cells
- braces, gates and small timelines

### Pass F: raster fragments

- photographs/video frames
- heatmaps or masks
- dense miniature timelines that cannot be recreated reliably

## 4. Color acquisition

Prefer direct sampling from flat regions of the reference. For diagrams with a coherent palette, define named colors once in the scene and reuse them. Typical families in the gold example:

- dark navy outline: approximately `#17335D` or `#284E7F`
- pale blue fill: approximately `#CFDCF0` / `#E7EDF6`
- light panel background: approximately `#F3F6FB`
- failure red: approximately `#B63228`
- failure pale red: approximately `#F6E6E4`
- accepted green: approximately `#7DA363` / pale green variants

Avoid independently sampling every antialiased edge pixel; use the flat interior color.

## 5. Text reconstruction

1. Record the visible text exactly, including case, punctuation and line breaks.
2. Use separate text boxes for distinct color/style runs.
3. Use explicit widths and heights; do not rely on automatic resizing.
4. Center module labels vertically, but top-align panel headings and labels where appropriate.
5. Use small margins (around 1–2 px at 100 px/in) to avoid clipping.
6. Validate text after rendering. Font substitution changes line wrapping; adjust the box width or explicit line breaks rather than shrinking everything.

## 6. Geometry reconstruction

### Rounded boxes

Approximate corners with 5–8 short line segments per quarter-circle. This creates stable geometry in Visio and LibreOffice.

### Ellipses and circles

Use 36–64 points depending on size. More points are useful for large cylinders; fewer are adequate for small prohibition circles.

### Arrows

Use one polyline and one filled triangle head. Shorten the line to the triangle base so it does not protrude through the head.

### Dashed panels

Use a consistent Visio line pattern and line weight. If a renderer displays the dashes differently, preserve the Visio pattern and visually check in the target application when possible.

### Cylinders

Use a filled outer body and a separate top ellipse outline. Place text in the body shape.

### Braces and equations

A brace can be a text glyph in a transparent box if the visual result is faithful. Equations with colored terms should be split into aligned text shapes.

## 7. Raster fragment policy

Rasterize only the irreducible content. For every crop:

- crop from the highest-resolution reference
- remove surrounding labels and vector borders
- preserve aspect ratio unless the source itself is stretched
- add vector border/shadow separately
- use PNG for lossless embedded fragments
- name the shape semantically

A good complex reconstruction may still contain many raster fragments, but they should occupy only the photographic/texture regions.

## 8. Iterative QA strategy

### Round 1: structure

Check page dimensions, panel bounds, module sequence and orientation.

### Round 2: typography

Check line breaks, text width, baseline and mixed-color terms.

### Round 3: styling

Check colors, stroke widths, dash patterns, corner radii and arrow heads.

### Round 4: micro-detail

Check small tokens, grids, warning symbols and tiny evidence bars.

### Round 5+: targeted correction

Use the amplified difference and checkerboard to identify the largest remaining local discrepancies. Modify one region at a time.

## 9. Completion decision

Stop only after:

- validation passes
- no critical content is missing
- global alignment is stable
- large difference regions have been addressed
- further changes mostly trade one renderer-specific text antialiasing difference for another

Document any remaining renderer/font uncertainty honestly.

## 10. Privacy-safe release gate

Before turning a successful one-off reconstruction into a reusable Skill or
public example:

1. Remove the user's source image, exact crops, scene coordinates, task-specific
   script, private labels, and intermediate comparison images.
2. Replace the worked example with a synthetic or explicitly redistributable
   benchmark; renaming the original files is not anonymization.
3. Normalize document metadata and archive timestamps for synthetic fixtures.
4. Search text files and nested VSDX XML/relationships for names, emails,
   identifiers, absolute paths, and build logs.
5. Strip EXIF and descriptive metadata from images.
6. Run `scripts/privacy_scan.py` and manually review domain-specific wording and
   visual content before distribution.

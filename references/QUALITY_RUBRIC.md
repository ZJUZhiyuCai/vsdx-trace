# Quality Rubric

Score each category from 0 to 5. A high-fidelity delivery should normally score at least 22/25, with no category below 4 except renderer-specific typography.

## 1. Global layout

- 0: unrelated layout
- 1: rough concept only
- 2: major regions present but badly scaled
- 3: correct structure with visible drift
- 4: close alignment; small local deviations
- 5: panel and module geometry visually overlaps the reference

## 2. Content and typography

- 0: missing or unreadable text
- 1: many transcription errors
- 2: most labels present but inconsistent
- 3: correct text with noticeable wrapping/font issues
- 4: correct text and near-matching placement
- 5: text, line breaks, color runs and hierarchy closely match

## 3. Shape and style fidelity

- 0: default generic shapes
- 1: wrong palette and line style
- 2: approximate palette, inconsistent strokes
- 3: broadly correct shapes and colors
- 4: close line weights, corners, dashes and icons
- 5: visually faithful microgeometry and consistent palette

## 4. Editability

- 0: full-page raster only
- 1: almost entirely raster
- 2: major blocks rasterized
- 3: main modules editable; many labels/images fused
- 4: all text and diagram primitives editable; only irreducible images raster
- 5: clean semantic shape decomposition, naming and reusable scene source

## 5. Reliability and verification

- 0: invalid file
- 1: opens unreliably
- 2: no validation or preview
- 3: structural validation passes
- 4: structural validation plus headless render passes
- 5: repeated visual QA, validation, preview/PDF, and target Visio test when available

## Diagnostic image metrics

Metrics are iteration aids, not acceptance criteria. Renderer-specific antialiasing and font substitution can materially change them.

For a dense academic diagram similar to the bundled gold example, approximate indicators of a strong iteration are:

- pixel similarity (`1 - normalized MAE`) around 0.88 or higher
- edge F1 around 0.68 or higher under a one-pixel tolerance
- no large concentrated regions in the amplified difference image

Do not optimize a metric by embedding the full reference on the editable page. Editability rules always override this shortcut.

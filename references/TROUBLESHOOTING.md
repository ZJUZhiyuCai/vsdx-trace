# Troubleshooting

## VSDX opens as a blank page

- Verify `visio/pages/pages.xml` references `page1.xml` through `pages.xml.rels`.
- Verify all page dimensions are positive.
- Verify `PinY` conversion uses bottom-left Visio coordinates.
- Run `scripts/validate_vsdx.py`.

## Diagram is vertically flipped

Use:

```text
PinY = (page_height_px - y - h/2) / PPI
```

For local polygon points, invert the point's Y within the shape bounding box.

## Images do not appear

- `ForeignData` must contain a child `<Rel r:id="..."/>`.
- `pageN.xml.rels` must target `../media/<file>.png`.
- `[Content_Types].xml` must define PNG.
- Ensure the media path exists in the ZIP.

## Text wraps differently

- Confirm the font is available in the render environment.
- Add explicit line breaks.
- Widen the text box before shrinking the font.
- Split mixed-style text into multiple text boxes.
- Keep margins very small for dense academic figures.

## Arrowheads disappear or look different

Use the bundled arrow primitive, which creates a separate filled triangle. Avoid relying only on a renderer-specific `EndArrow` code.

## Rounded corners are jagged

Increase `corner_segments` from 6 to 8 or 10. Do not use excessive segments for tiny boxes.

## LibreOffice produces a different font

LibreOffice is a compatibility check, not proof of Microsoft Visio's exact typography. Use common fonts, explicit line breaks and a reference page. State that desktop Visio was not tested unless it actually was.

## Validation warns about a bitmap-only reconstruction

The main page likely contains only one full-page `Foreign` shape. Rebuild text, panels and arrows as native shapes; move the full image to the reference page.

## Visual score improves but editability worsens

Reject the change. The objective is high fidelity under an editability constraint, not raw pixel similarity.

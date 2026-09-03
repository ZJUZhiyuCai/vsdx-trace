# VSDX Open XML Notes

## Package structure

A `.vsdx` file is a ZIP/OPC package. The generator writes at least:

```text
[Content_Types].xml
_rels/.rels
docProps/core.xml
docProps/app.xml
visio/document.xml
visio/_rels/document.xml.rels
visio/windows.xml
visio/pages/pages.xml
visio/pages/_rels/pages.xml.rels
visio/pages/page1.xml
```

Pages containing images also include:

```text
visio/pages/_rels/page1.xml.rels
visio/media/p1_image_1.png
```

## Required relationship pattern

- Package root → `visio/document.xml`
- `document.xml` → `pages/pages.xml`
- `pages.xml` → each `pageN.xml`
- `pageN.xml` → embedded media files

The `<Rel r:id="..."/>` element belongs inside the Visio page/page shape XML. The actual relationship target belongs in the corresponding `.rels` part.

## Shape coordinate model

Visio uses inch values and a bottom-left page origin. A 2-D shape uses:

- `PinX`, `PinY`
- `Width`, `Height`
- `LocPinX`, `LocPinY`
- `Angle`

Geometry sections use local shape coordinates, also bottom-up.

## Basic vector shape

```xml
<Shape ID="1" Name="Panel" NameU="Panel" Type="Shape"
       LineStyle="0" FillStyle="0" TextStyle="0">
  <Cell N="PinX" V="5"/>
  <Cell N="PinY" V="3"/>
  <Cell N="Width" V="4"/>
  <Cell N="Height" V="2"/>
  <Cell N="LocPinX" V="2"/>
  <Cell N="LocPinY" V="1"/>
  <Cell N="FillForegnd" V="#F3F6FB"/>
  <Cell N="FillPattern" V="1"/>
  <Cell N="LineColor" V="#284E7F"/>
  <Cell N="LinePattern" V="2"/>
  <Cell N="LineWeight" V="0.03"/>
  <Section N="Geometry" IX="0">...</Section>
</Shape>
```

## Text

Text formatting uses a Character row and Paragraph row. Font size is stored as inches with `U="PT"`; convert points by `pt / 72`.

```xml
<Section N="Character">
  <Row IX="0">
    <Cell N="Font" V="0"/>
    <Cell N="Color" V="#000000"/>
    <Cell N="Size" V="0.3333333333" U="PT"/>
    <Cell N="Style" V="1"/>
  </Row>
</Section>
<Section N="Paragraph">
  <Row IX="0"><Cell N="HorzAlign" V="1"/></Row>
</Section>
<Text>Example</Text>
```

Style bit flags commonly used by this generator: 1 bold, 2 italic, 4 underline.

## Embedded bitmap shape

```xml
<Shape ID="8" Type="Foreign" LineStyle="0" FillStyle="0" TextStyle="0">
  ... XForm cells ...
  <Cell N="ImgOffsetX" V="0"/>
  <Cell N="ImgOffsetY" V="0"/>
  <Cell N="ImgWidth" V="2.2"/>
  <Cell N="ImgHeight" V="1.5"/>
  <ForeignData ForeignType="Bitmap" CompressionType="PNG">
    <Rel r:id="rId1"/>
  </ForeignData>
</Shape>
```

The relationship type is the standard Open XML image relationship.

## Compatibility choices

- Use numeric, unique Shape IDs.
- Use simple `MoveTo` and `LineTo` geometry where practical.
- Avoid unsupported SVG-like features inside VSDX.
- Use PNG for embedded crops.
- Keep the VSDX package as the source of truth; PDF/PNG are only QA outputs.

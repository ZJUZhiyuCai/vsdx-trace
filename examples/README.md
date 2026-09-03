# Worked examples

## Generic scene template

Build and validate the bundled template:

```bash
python scripts/build_from_scene.py \
  assets/templates/scene-template.json \
  work/template-output.vsdx \
  --manifest work/template-output.manifest.json
python scripts/validate_vsdx.py work/template-output.vsdx \
  --output work/template-output.validation.json
```

## Privacy-safe full reconstruction case

`synthetic_event_routing_case.py` procedurally creates an abstract reference
figure, 12 synthetic local raster frames, a complete scene JSON, and a two-page
editable VSDX. It demonstrates a dense 269-shape build without reusing any
user-provided image, wording, identity, organization, paper title, or private
path.

```bash
python examples/synthetic_event_routing_case.py \
  --work-dir work/synthetic-event-routing \
  --output work/synthetic-event-routing/synthetic_event_routing_editable.vsdx
```

Use the case as an implementation reference. Do not copy its coordinates into
unrelated figures; reconstruct each new reference from its own pixel geometry.

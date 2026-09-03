# Contributing to VSDX Trace

Thank you for helping improve editable diagram reconstruction. Small, focused
changes with observable tests are easiest to review.

## Before you start

- Search existing issues and discussions before opening a duplicate.
- Open an issue before a large schema change, new dependency, or breaking
  behavior change.
- Never contribute private reference images, customer data, local paths,
  personal identifiers, or task-specific generated artifacts.
- Use synthetic or explicitly redistributable fixtures for every test and
  example.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Test locally

```bash
ruff check .
pytest
python scripts/privacy_scan.py .
```

For changes that affect rendering, also run LibreOffice/Poppler QA and inspect
the overlay, checkerboard, and amplified difference—not only the numeric score.

## Skill changes

Keep `SKILL.md` focused on decisions that materially improve reconstruction.
Place detailed schemas and conditional procedures in `references/`. Preserve
automatic invocation unless a change is explicitly intended to alter routing.

If you change the skill name, description, UI metadata, file layout, or version:

1. keep `SKILL.md`, `agents/openai.yaml`, `VERSION`, and package reports aligned;
2. run the skill validator;
3. rebuild package manifests and archives;
4. document user-visible behavior in `CHANGELOG.md`.

## Pull requests

- Use a descriptive title and explain the user-facing reason for the change.
- Keep generated files out of the commit unless they are deterministic fixtures.
- Add or update tests for changed behavior.
- Include the exact commands used to validate the change.
- Confirm the privacy checklist in the pull-request template.

By contributing, you agree that your contribution is licensed under the
repository's MIT License.

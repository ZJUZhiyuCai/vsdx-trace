# Release process

VSDX Trace follows Semantic Versioning. A release tag must match the version in
`VERSION`, `SKILL.md`, `SKILL_TEST_REPORT.json`, `PRIVACY_AUDIT.json`, and
`evals/evals.json`.

## Checklist

1. Update `CHANGELOG.md` and all version fields.
2. Run `ruff check .` and `pytest` on a clean checkout.
3. Run the skill validator and the privacy scanner with project-specific deny terms.
4. Rebuild both skill archives and verify every manifest hash.
5. Inspect the Gold Standard render and comparison report after rendering changes.
6. Merge through a reviewed pull request with green CI and CodeQL checks.
7. Create an annotated `vMAJOR.MINOR.PATCH` tag from `main` and push it.

The release workflow validates the tag, builds Core and Full skill archives,
generates `SHA256SUMS`, and publishes all three files as GitHub Release assets.

Do not publish a release containing user references, local work directories,
task-specific crops, private labels, or build logs.

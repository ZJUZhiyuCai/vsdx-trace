# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 2.x | Yes |
| 1.x and earlier | No |

## Report a vulnerability

Do not open a public issue for a suspected vulnerability. Use
[GitHub private vulnerability reporting](https://github.com/ZJUZhiyuCai/vsdx-trace/security/advisories/new)
and include:

- the affected version and component;
- a minimal synthetic reproduction;
- expected impact;
- any known mitigation.

Never attach a private customer diagram or user reference image. Replace sensitive
material with the smallest synthetic fixture that reproduces the issue.

Maintainers aim to acknowledge complete reports within seven days and will
coordinate remediation and disclosure through the private advisory.

## Security-sensitive areas

Reports are especially useful for archive path traversal, unsafe XML processing,
unexpected external command execution, generated-package corruption, or privacy
scanner bypasses involving VSDX, ZIP, image, JSON, or path inputs.

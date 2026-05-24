# CHANGELOG

## 1.0.6 (unreleased)

- Added GitHub repository, issue tracker, and changelog links to PyPI project page.
- Trimmed PyPI package description to user-facing content; moved development and release workflow docs to `CONTRIBUTING.md`.

## 1.0.5 (2026-05-23)

Initial PyPI release.

- PDM plugin that prepends configured project directories to `PATH` before each `pdm run` invocation.
- Opt-in per project via `[tool.pdm.plugin.bin-dir] dirs = [...]` in `pyproject.toml`. No effect if the section is absent.
- Default directory list is empty (no directories added unless explicitly configured).
- Adds `pdm bin-dir [show|set|add]` subcommand for inspecting and updating configuration.
- Requires PDM 2.0 or later.

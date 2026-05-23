# CHANGELOG

## 1.0.0 (unreleased)

Initial release.

- PDM plugin that prepends configured project directories to `PATH` before each `pdm run` invocation.
- Default directory: `bin` (relative to project root).
- Configurable via `[tool.pdm.plugin.bin-dir] dirs = [...]` in `pyproject.toml`.
- Adds `pdm bin-dir [show|set|add]` command for inspecting and updating configuration.

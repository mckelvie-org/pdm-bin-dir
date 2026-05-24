# pdm-bin-dir

[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/mckelvie-org/pdm-bin-dir/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/badge/pypi-v1.0.7rc1-blue.svg)](https://test.pypi.org/project/pdm-bin-dir/1.0.7rc1/)
[![Python versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue.svg)](https://pypi.org/project/pdm-bin-dir/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

`pdm-bin-dir` is a [PDM](https://pdm-project.org/) plugin that automatically prepends additional project directories to `PATH` when running commands via PDM. This lets you place helper scripts alongside your project and run them as plain commands — no prefix or activation needed.

## Requirements

- Python 3.10 or later
- PDM 2.0 or later

## Installation

Install the plugin into PDM's own environment:

```bash
pdm self add pdm-bin-dir
```

## Usage

The plugin is **opt-in per project**: it has no effect unless `[tool.pdm.plugin.bin-dir]` is present in the project's `pyproject.toml`. Once configured, the listed directories are prepended to `PATH` before every `pdm run …` invocation.

### Configuration

Add to your project's `pyproject.toml`:

```toml
[tool.pdm.plugin.bin-dir]
dirs = ["bin", "scripts"]
```

Paths are relative to the project root. Absolute paths are also accepted. The default is an empty list (no directories added).

### `pdm bin-dir` command

The plugin registers a `bin-dir` sub-command for inspecting and changing the configuration:

```bash
# Show current configured directories (JSON array)
pdm bin-dir show

# Replace the list
pdm bin-dir set bin scripts

# Append to the list (duplicates are silently skipped)
pdm bin-dir add tools
```

Changes made via `set` / `add` are written back to `pyproject.toml`.

## License

MIT. See [LICENSE](LICENSE).

---

For development and release workflow documentation, see [CONTRIBUTING.md](https://github.com/mckelvie-org/pdm-bin-dir/blob/main/CONTRIBUTING.md).

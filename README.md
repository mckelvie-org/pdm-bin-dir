# pdm-bin-dir

[![CI](https://github.com/mckelvie-org/pdm-bin-dir/actions/workflows/ci.yml/badge.svg)](https://github.com/mckelvie-org/pdm-bin-dir/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/pdm-bin-dir.svg)](https://pypi.org/project/pdm-bin-dir/)
[![Python versions](https://img.shields.io/pypi/pyversions/pdm-bin-dir.svg)](https://pypi.org/project/pdm-bin-dir/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

`pdm-bin-dir` is a [PDM](https://pdm-project.org/) plugin that automatically prepends additional project directories to `PATH` when running commands via PDM. This lets you place helper scripts alongside your project and run them as plain commands — no prefix or activation needed.

## Installation

Install the plugin into PDM's own environment:

```bash
pdm plugin add pdm-bin-dir
```

## Usage

The plugin is **opt-in per project**: it has no effect unless `[tool.pdm.plugin.bin-dir]` is present in the project's `pyproject.toml`. Once configured, the listed directories are prepended to `PATH` before every `pdm run …` invocation.

### Configuration

Override the directories in `pyproject.toml`:

```toml
[tool.pdm.plugin.bin-dir]
dirs = ["bin", "scripts"]
```

Paths are relative to the project root. Absolute paths are also accepted.

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

## Development

This project uses [PDM](https://pdm-project.org/) for dependency management,
linting, type checking, and testing.

```bash
pdm install -G dev
pdm run lint       # ruff check
pdm run typecheck  # mypy
pdm run test       # pytest
pdm build
```

## Publishing

Releases are managed through GitHub Actions using a three-channel model:

| Channel | Branch | Tag format | Index |
|---|---|---|---|
| dev | `main` | — (no publish) | — |
| rc | `rc/<x.y.z>` | `rc-v<x.y.z>-rc.<n>` | TestPyPI |
| prod | `prod/<x.y.z>` | `v<x.y.z>` | PyPI |

### Version invariant

`main` always carries `X.Y.Z-dev.N`.  The `x.y.z` portion of any RC or
production release always matches the commit on `main` from which it was cut —
only the qualifier suffix changes.

### Release workflow

**Bump dev version** — increment the version on `main`.

```bash
bin/bump-dev [dev|patch|minor|major]   # edits pyproject.toml, does not commit
```

| `bump_type` | Example |
|---|---|
| `dev` | `1.0.0-dev.1` → `1.0.0-dev.2` |
| `patch` | `1.0.0-dev.2` → `1.0.1-dev.1` |
| `minor` | `1.0.0-dev.2` → `1.1.0-dev.1` |
| `major` | `1.0.0-dev.2` → `2.0.0-dev.1` |

Also available remotely via `Actions → Bump dev version → Run workflow` for
cases where a local checkout is not convenient.

**`bin/cut-rc`** (run on `main`) — create a release candidate.

Reads `X.Y.Z-dev.N` from `pyproject.toml`, auto-increments the rc counter
from existing tags, creates branch `rc/X.Y.Z` with version `X.Y.Z-rc.N`,
and pushes — triggering `Publish TestPyPI`.

**`bin/cut-prod`** (run on `rc/<x.y.z>`) — promote to production.

Strips the rc qualifier, creates branch `prod/X.Y.Z` with the clean `X.Y.Z`
version, and pushes — triggering `Publish`, which tags the commit `vX.Y.Z`
and auto-bumps `main` to `X.Y.(Z+1)-dev.1` after a successful PyPI push.

### Guards

Both publish workflows validate that:

- The branch version matches `pyproject.toml`'s version.
- The version format matches the target index (stable for PyPI, `-rc.N` for
  TestPyPI).
- The version does not already exist on the target index.
- Lint, type checks, and tests pass.

### Install-path smoke test

Use the **Install Smoke Test** workflow to verify an install without publishing
or bumping a version:

- `source=github` with a `git_ref` — installs directly from the repository.
- `source=testpypi` with a `version` — installs an already-uploaded TestPyPI
  build.

## Supported Python Versions

Python 3.10 and later.

## License

MIT. See [LICENSE](LICENSE).

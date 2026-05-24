# Contributing

This project uses [PDM](https://pdm-project.org/) for dependency management, linting, type checking, and testing.

## Development setup

```bash
pdm install -G dev
pdm run lint       # ruff check
pdm run typecheck  # mypy
pdm run test       # pytest
pdm build
```

## Release workflow

Releases follow a three-channel model:

| Channel | Branch | Tag format     | Index    |
|---------|--------|----------------|----------|
| dev     | `main` | —              | —        |
| rc      | `rc`   | `v<x.y.z>-rc.<n>` | TestPyPI |
| prod    | `prod` | `v<x.y.z>`     | PyPI     |

`main` always carries `X.Y.Z-dev.N`. The `rc` and `prod` branches are
force-pushed on each release; tags provide the durable history.

### Bump the dev version

```bash
bin/bump-dev [dev|patch|minor|major]   # edits pyproject.toml, does not commit
```

| `bump_type` | Example |
|-------------|---------|
| `dev`       | `1.0.0-dev.1` → `1.0.0-dev.2` |
| `patch`     | `1.0.0-dev.2` → `1.0.1-dev.1` |
| `minor`     | `1.0.0-dev.2` → `1.1.0-dev.1` |
| `major`     | `1.0.0-dev.2` → `2.0.0-dev.1` |

Commit and push to `main` before cutting a release.

### Cut a release candidate

Run from `main`:

```bash
bin/cut-rc
```

Reads `X.Y.Z-dev.N` from `pyproject.toml`, finds the next unused rc counter
from existing `v<x.y.z>-rc.*` tags, sets the version to `X.Y.Z-rc.N` in a
worktree, and force-pushes to the `rc` branch — triggering `Publish TestPyPI`.

After a successful publish the workflow tags the commit `v<x.y.z>-rc.<n>`.

### Cut a production release

Run from `main`:

```bash
bin/cut-prod [RC_REF]
```

`RC_REF` is optional. Resolution order:
1. Explicit argument (tag, sha, or bare version like `1.0.5-rc.1`).
2. `HEAD`, if `pyproject.toml` in the working tree carries an `X.Y.Z-rc.N` version.
3. `origin/rc` (the latest rc commit).

Strips the rc qualifier, commits to a worktree, and force-pushes to `prod` —
triggering `Publish`, which tags the commit `v<x.y.z>` and auto-bumps `main`
to `X.Y.(Z+1)-dev.1` after a successful PyPI push.

### Guards

Both publish workflows validate that:

- The version in `pyproject.toml` matches the expected format for the target index.
- The version does not already exist on the target index.
- Lint, type checks, and tests pass.

### Smoke test

Use the **Install Smoke Test** workflow to verify an install without publishing:

```bash
# From GitHub source
gh workflow run install-smoke.yml --field source=github --field git_ref=main

# From TestPyPI
gh workflow run install-smoke.yml --field source=testpypi --field version=1.0.5rc1
```

Two jobs run in parallel: `smoke-pip` (pip install + import/export assertions)
and `smoke-pdm` (`pdm self add` + functional PATH test in a real PDM project).

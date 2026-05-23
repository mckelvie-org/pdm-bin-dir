"""Tests for pdm-bin-dir plugin."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import pdm_bin_dir
from pdm_bin_dir import (
    CONFIG_DIRS_KEY,
    CONFIG_DIRS_SUBKEY,
    CONFIG_GROUP,
    DEFAULT_BIN_DIRS,
    BinDirCommand,
    _add_bin_dirs_to_path,
    _get_abspath,
    _normalize_relpath,
    get_bin_dirs,
    get_bin_reldirs,
    plugin,
    update_bin_dirs,
)


def _mock_project(tmpdir: str, config: dict[str, Any]) -> MagicMock:
    """Return a minimal mock PDM Project backed by the given config dict."""
    project = MagicMock()
    project.root = Path(tmpdir)
    project.pyproject.open_for_read.return_value = config
    project.pyproject.open_for_write.return_value = config
    return project


# ---------------------------------------------------------------------------
# Module-level exports and constants
# ---------------------------------------------------------------------------

def test_version() -> None:
    assert isinstance(pdm_bin_dir.__version__, str)
    assert pdm_bin_dir.__version__ != ""


def test_constants() -> None:
    assert CONFIG_GROUP == "tool.pdm.plugin.bin-dir"
    assert CONFIG_DIRS_SUBKEY == "dirs"
    assert CONFIG_DIRS_KEY == "tool.pdm.plugin.bin-dir.dirs"
    assert DEFAULT_BIN_DIRS == []


def test_exports_callable() -> None:
    assert callable(plugin)
    assert callable(get_bin_reldirs)
    assert callable(get_bin_dirs)
    assert issubclass(BinDirCommand, object)


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def test_get_abspath_relative() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        result = _get_abspath(project, "bin")
        assert result == os.path.join(tmpdir, "bin")
        assert os.path.isabs(result)


def test_normalize_relpath_inside_project() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert _normalize_relpath(project, "bin") == "bin"
        assert _normalize_relpath(project, "scripts/tools") == os.path.join("scripts", "tools")


def test_normalize_relpath_outside_project() -> None:
    with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
        project = _mock_project(tmpdir, {})
        result = _normalize_relpath(project, outside)
        assert os.path.isabs(result)


# ---------------------------------------------------------------------------
# get_bin_reldirs
# ---------------------------------------------------------------------------

def test_get_bin_reldirs_default() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert get_bin_reldirs(project) == []


def test_get_bin_reldirs_configured_list() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["scripts", "tools"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert get_bin_reldirs(project) == ["scripts", "tools"]


def test_get_bin_reldirs_configured_empty() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": []}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert get_bin_reldirs(project) == []


def test_get_bin_reldirs_configured_string() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": "scripts"}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert get_bin_reldirs(project) == ["scripts"]


def test_get_bin_reldirs_invalid_raises() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": 42}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        with pytest.raises(ValueError):
            get_bin_reldirs(project)


# ---------------------------------------------------------------------------
# get_bin_dirs
# ---------------------------------------------------------------------------

def test_get_bin_dirs_default_empty() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert get_bin_dirs(project) == []


def test_get_bin_dirs_absolute() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["bin"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        result = get_bin_dirs(project)
        assert result == [os.path.join(tmpdir, "bin")]
        assert all(os.path.isabs(p) for p in result)


def test_get_bin_dirs_custom() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["scripts", "tools"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        result = get_bin_dirs(project)
        assert result == [
            os.path.join(tmpdir, "scripts"),
            os.path.join(tmpdir, "tools"),
        ]


# ---------------------------------------------------------------------------
# update_bin_dirs
# ---------------------------------------------------------------------------

def test_update_bin_dirs_set_new() -> None:
    config: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        changed = update_bin_dirs(project, ["scripts"], flush=False)
        assert changed is True


def test_update_bin_dirs_no_change() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["bin"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        changed = update_bin_dirs(project, ["bin"], flush=False)
        assert changed is False


def test_update_bin_dirs_remove_config() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["scripts"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        changed = update_bin_dirs(project, None, flush=False)
        assert changed is True


def test_update_bin_dirs_remove_when_not_set() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        changed = update_bin_dirs(project, None, flush=False)
        assert changed is False


# ---------------------------------------------------------------------------
# _add_bin_dirs_to_path
# ---------------------------------------------------------------------------

def test_add_bin_dirs_to_path_prepends() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["bin"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        expected = os.path.join(tmpdir, "bin")
        old_path = os.environ.get("PATH", "")
        try:
            _add_bin_dirs_to_path(project=project)
            new_entries = os.environ["PATH"].split(os.pathsep)
            assert new_entries[0] == expected
        finally:
            os.environ["PATH"] = old_path


def test_add_bin_dirs_to_path_no_op_when_unconfigured() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        old_path = os.environ.get("PATH", "")
        try:
            _add_bin_dirs_to_path(project=project)
            assert os.environ.get("PATH", "") == old_path
        finally:
            os.environ["PATH"] = old_path


def test_add_bin_dirs_to_path_no_duplicate() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": ["bin"]}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        bin_dir = os.path.join(tmpdir, "bin")
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = bin_dir + os.pathsep + old_path
        try:
            _add_bin_dirs_to_path(project=project)
            entries = os.environ["PATH"].split(os.pathsep)
            assert entries.count(bin_dir) == 1
        finally:
            os.environ["PATH"] = old_path


def test_add_bin_dirs_to_path_empty_dirs() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"dirs": []}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        old_path = os.environ.get("PATH", "")
        try:
            _add_bin_dirs_to_path(project=project)
            assert os.environ.get("PATH", "") == old_path
        finally:
            os.environ["PATH"] = old_path

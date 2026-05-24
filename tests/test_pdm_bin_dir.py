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
    CONFIG_GROUP,
    DEBUG_ENV_VAR,
    DEBUG_KEY,
    DEFAULT_BIN_DIRS,
    BinDirCommand,
    _add_bin_dirs_to_path,
    _get_abspath,
    _is_debug_enabled,
    _is_debug_env_var_enabled,
    _is_debug_pyproject_enabled,
    _normalize_relpath,
    dprint,
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
    assert CONFIG_DIRS_KEY == "tool.pdm.plugin.bin-dir.dirs"
    assert DEBUG_ENV_VAR == "PDM_BIN_DIR_DEBUG"
    assert DEBUG_KEY == "tool.pdm.plugin.bin-dir.debug"
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


# ---------------------------------------------------------------------------
# Debug: _is_debug_env_var_enabled
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_debug_caches() -> None:
    _is_debug_env_var_enabled.cache_clear()
    _is_debug_pyproject_enabled.cache_clear()


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "True", "YES", "ON", "TRUE"])
def test_debug_env_var_truthy(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, val)
    _is_debug_env_var_enabled.cache_clear()
    assert _is_debug_env_var_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "no", "off", "False", "NO"])
def test_debug_env_var_falsy(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, val)
    _is_debug_env_var_enabled.cache_clear()
    assert _is_debug_env_var_enabled() is False


def test_debug_env_var_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    _is_debug_env_var_enabled.cache_clear()
    assert _is_debug_env_var_enabled() is None


def test_debug_env_var_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, "  ")
    _is_debug_env_var_enabled.cache_clear()
    assert _is_debug_env_var_enabled() is None


# ---------------------------------------------------------------------------
# Debug: _is_debug_pyproject_enabled
# ---------------------------------------------------------------------------

def test_debug_pyproject_enabled() -> None:
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"debug": True}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert _is_debug_pyproject_enabled(project) is True


def test_debug_pyproject_disabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert _is_debug_pyproject_enabled(project) is False


def test_debug_pyproject_none_project() -> None:
    assert _is_debug_pyproject_enabled(None) is False


# ---------------------------------------------------------------------------
# Debug: _is_debug_enabled (precedence)
# ---------------------------------------------------------------------------

def test_debug_enabled_env_true_overrides_pyproject_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, "1")
    _is_debug_env_var_enabled.cache_clear()
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert _is_debug_enabled(project) is True


def test_debug_enabled_env_false_overrides_pyproject_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, "0")
    _is_debug_env_var_enabled.cache_clear()
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"debug": True}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert _is_debug_enabled(project) is False


def test_debug_enabled_falls_back_to_pyproject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    _is_debug_env_var_enabled.cache_clear()
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"debug": True}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        assert _is_debug_enabled(project) is True


def test_debug_enabled_both_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    _is_debug_env_var_enabled.cache_clear()
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        assert _is_debug_enabled(project) is False


# ---------------------------------------------------------------------------
# Debug: dprint
# ---------------------------------------------------------------------------

def test_dprint_writes_to_stderr_when_enabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    _is_debug_env_var_enabled.cache_clear()
    config = {"tool": {"pdm": {"plugin": {"bin-dir": {"debug": True}}}}}
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, config)
        dprint(project, "hello", "world")
    captured = capsys.readouterr()
    assert "hello" in captured.err
    assert "world" in captured.err


def test_dprint_silent_when_disabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    _is_debug_env_var_enabled.cache_clear()
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        dprint(project, "should not appear")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.err


def test_dprint_via_env_var(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, "1")
    _is_debug_env_var_enabled.cache_clear()
    with tempfile.TemporaryDirectory() as tmpdir:
        project = _mock_project(tmpdir, {})
        dprint(project, "env-triggered message")
    captured = capsys.readouterr()
    assert "env-triggered message" in captured.err

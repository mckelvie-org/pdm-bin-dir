"""
PDM plugin that allows additional directories other than {VENV_BASE}/bin to be added to the front of the PATH environment variable when running commands in the project.

By default it will add the `{PROJECT_ROOT}/bin` directory. This can be overridden in pyproject.toml.

Example:
```toml
[tool.pdm.plugin.bin-dir]
dirs=["bin", "scripts"]
```

For convenience, the plugin also adds a `pdm bin-dir` command to display or set the configured paths.

Example usage:
```bash
   pdm bin-dir show                # Display the current configured bin directories.
   pdm bin-dir set <relpath...>    # Set the bin directories to zero or more custom relative path(s) from the project root.
   pdm bin-dir add <relpath...>    # Add one or more custom relative path(s) from the project root to the end of the existing configured bin directories.
```

"""
from __future__ import annotations

import json
import os
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from copy import deepcopy
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Any, ClassVar

from pdm.cli.commands.base import BaseCommand
from pdm.core import Core
from pdm.project import Project
from pdm.signals import pre_invoke
from typing_extensions import override

try:
    __version__ = package_version("pdm-bin-dir")
except PackageNotFoundError:
    # Source tree import before installation.
    __version__ = "0.0.0"

__all__ = [
    "BinDirCommand",
    "plugin",
    "get_bin_reldirs",
    "get_bin_dirs",
    "CONFIG_GROUP",
    "CONFIG_DIRS_SUBKEY",
    "CONFIG_DIRS_KEY",
    "DEFAULT_BIN_DIRS",
]

CONFIG_GROUP = "tool.pdm.plugin.bin-dir"
CONFIG_DIRS_SUBKEY = "dirs"
CONFIG_DIRS_KEY = f"{CONFIG_GROUP}.{CONFIG_DIRS_SUBKEY}"

DEFAULT_BIN_DIRS: list[str] = []
"""The default list of bin directories to add to PATH if not configured in pyproject.toml.

Defaults to empty so the plugin has no effect on projects that have not explicitly opted in
via ``[tool.pdm.plugin.bin-dir]`` in their ``pyproject.toml``.
"""


def _read_pyproject_key(project: Project, key: str, default: Any=None) -> object:
    """Helper function to read a key from the pyproject.toml configuration.
       if the key contains dots, it will be treated as a nested key.
    """
    if key == "":
        raise ValueError("Key cannot be empty")
    cfg = project.pyproject.open_for_read()
    val: object = cfg
    for part in key.split("."):
        if part == "":
            raise ValueError(f"Invalid key with empty part: {key!r}")
        if not isinstance(val, Mapping):
            return default
        val = val.get(part, default)
    if isinstance(val, (Mapping, Sequence)):
        val = deepcopy(val)
    return val

def _write_pyproject_key(project: Project, key: str, value: Any, flush: bool=True, show_message: bool=True) -> None:
    """Helper function to write a key to the pyproject.toml configuration.
       if the key contains dots, it will be treated as a nested key and parent containers will be created as needed.
    """
    cfg = project.pyproject.open_for_write()
    parent: object = cfg
    if key == "":
        raise ValueError("Key cannot be empty")
    parts = key.split(".")
    for part in parts[:-1]:
        if part == "":
            raise ValueError(f"Invalid key with empty part: {key!r}")
        if not isinstance(parent, MutableMapping):
            raise ValueError(f"Invalid pyproject.toml structure: expected MutableMapping above {part!r} in {key!r}")
        if part not in parent:
            parent[part] = {}
        parent = parent[part]
    if not isinstance(parent, MutableMapping):
        raise ValueError(f"Invalid pyproject.toml structure: expected MutableMapping above {parts[-1]!r} in {key!r}")
    parent[parts[-1]] = value
    if flush:
        project.pyproject.write(show_message=show_message)

def _delete_pyproject_key(project: Project, key: str, flush: bool=True, show_message: bool=True) -> None:
    """Helper function to delete a key in the pyproject.toml if it exists.
       if the key contains dots, it will be treated as a nested key.
       Parent containers are not deleted, even if they become empty after deletion.
    """
    cfg = project.pyproject.open_for_write()
    parent: object = cfg
    if key == "":
        raise ValueError("Key cannot be empty")
    parts = key.split(".")
    for part in parts[:-1]:
        if part == "":
            raise ValueError(f"Invalid key with empty part: {key!r}")
        if not isinstance(parent, MutableMapping):
            return
        if part not in parent:
            return
        parent = parent[part]
    if not isinstance(parent, MutableMapping):
        return
    if parts[-1] not in parent:
        return
    del parent[parts[-1]]
    if flush:
        project.pyproject.write(show_message=show_message)
        
def get_bin_reldirs(project: Project) -> list[str]:
    """Returns the bin directories exactly as configured in pyproject.toml, or the default if not configured.
       The paths are returned as-is without normalization, and may be absolute or relative."""
    any_result = _read_pyproject_key(project, CONFIG_DIRS_KEY)
    result: list[str]
    if any_result is None:
        result = DEFAULT_BIN_DIRS
    elif isinstance(any_result, str):
        result = [] if any_result == "" else [any_result]
    elif isinstance(any_result, Sequence):
        if len(any_result) > 0 and any(not isinstance(item, str) for item in any_result):
            raise ValueError(f"Invalid {CONFIG_DIRS_KEY} in project configuration: {any_result}")
        result = list(any_result)
    else:
        raise ValueError(f"Invalid {CONFIG_DIRS_KEY} in project configuration: {any_result}")

    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise ValueError(f"Invalid {CONFIG_DIRS_KEY} in project configuration: {result}")
    return result

def _get_abspath(project: Project, relpath: str) -> str:
    """Resolves a path to absolute form using the project root as a base"""
    return os.path.abspath(os.path.join(project.root, relpath))

def _get_abs_paths(project: Project, relpaths: Iterable[str]) -> list[str]:
    """Resolves a sequence of paths to absolute form using the project root as a base"""
    return [_get_abspath(project, relpath) for relpath in relpaths]

def _normalize_relpath(project: Project, relpath: str) -> str:
    """Takes a path, which may either be absolute or relative to the project root, and returns a path that is absolute if it is
       outsude the project, or relative if within."""
    result = _get_abspath(project, relpath)
    if result.startswith(str(project.root)):
        result = os.path.relpath(result, project.root)
    return result

def _normalize_relpaths(project: Project, relpaths: Iterable[str]) -> list[str]:
    """Takes a sequence of paths, which may either be absolute or relative to the project root, and returns a list of paths that are absolute if they are
       outsude the project, or relative if within."""
    return [_normalize_relpath(project, relpath) for relpath in relpaths]

def get_bin_dirs(project: Project) -> list[str]:
    """Returns the resolved configured list of absolute bin directories."""
    reldirs = get_bin_reldirs(project)
    return _get_abs_paths(project, reldirs)

def update_bin_dirs(project: Project, new_dirs: list[str] | None, flush: bool=True, show_message: bool=True) -> bool:
    """Replaces the configured bin directories with the given list of new directories, and writes to pyproject.toml if flush is True.
       The new_dirs should be relative paths from the project root, or absolute paths. They are recorded exactly as given. If
       None is given, the configuration will be removed and the default will be used instead.

    Args:
        project (Project): The PDM project instance.
        new_dirs (list[str] | None): The new list of bin directories to set, or None to remove the configuration and use the default.
        flush (bool, optional): Whether to write the changes to pyproject.toml. Defaults to True.
        show_message (bool, optional): Whether to display a message when writing to pyproject.toml. Defaults to True.

    Raises:
        ValueError: If the provided directory list is invalid.

    Returns:
        bool: True if the bin directories were changed, False otherwise.
    """
    if new_dirs is None:
        old_value = _read_pyproject_key(project, CONFIG_DIRS_KEY)
        if old_value is None:
            return False
        _delete_pyproject_key(project, CONFIG_DIRS_KEY, flush=flush, show_message=show_message)
    else:
        if not isinstance(new_dirs, list) or not all(isinstance(item, str) for item in new_dirs):
            raise ValueError(f"Invalid directory list provided to `pdm bin-dir update`: {new_dirs}")
        old_dirs = get_bin_reldirs(project)
        if old_dirs == new_dirs:
            return False
        _write_pyproject_key(project, CONFIG_DIRS_KEY, new_dirs, flush=flush, show_message=show_message)
        
    return True

class BinDirCommand(BaseCommand):
    """
       Display or configure additional environment search path directories for the project
    """
    # Note: the ArgParse help string for this command is extracted by pdm from the above docstring of this class, so it should be kept appropriate
    # for that purpose rather than internal dev-facing.
    
    cmd_name: ClassVar[str] = "bin-dir"
        
    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        """Called by PDM at startup to configure the argument parser for this command."""

        parser.epilog = "If no subcommand is given, the current configured directories will be displayed."
        subparsers = parser.add_subparsers(dest="bindir_subcmd", title="subcommands", help="Action to perform on the project setting.")
        subparsers.required = False
        
        subparsers.add_parser("show", help="Display the configired bin directories as represented in pyproject.toml. By default, JSON list encoding is used")

        set_parser = subparsers.add_parser("set", help="Set the bin directories to the given relative paths")
        set_parser.add_argument("relpaths", nargs="*", help="Relative paths from the project root to set as bin directories, separated by space. If omitted, no dirs will be searched.")

        add_parser = subparsers.add_parser("add", help="Add the given relative paths to the existing bin directories")
        add_parser.add_argument("relpaths", nargs="*", help="Relative paths from the project root to add as bin directories, separated by space. If omitted, has no effect.")
        
    def handle_show(self, project: Project, options: Namespace) -> int:
        """`pdm bin-dir show` command handler. Display current configured bin directories to stdout.

        Encodes as a JSON array of strings. Displays the relative paths as configured in pyproject.toml.

        Args:
            project (Project):    The PDM project instance.
            options (Namespace):  The parsed command line options.

        Returns:
            int: The exit code of the command. 0 indicates success, non-zero indicates failure.
        """
        # TODO: Add command options to control the output format, and whether to display absolute or relative paths.
        current_dirs = get_bin_reldirs(project)
        print(json.dumps(current_dirs))
        return 0
   
    def handle_set(self, project: Project, options: Namespace) -> int:
        """Handle the `pdm bin-dir set` command. Replace the configured bin directories with the given list of relative paths, and write to pyproject.toml.
        
        By default, the given paths are normalized to be relative to the project root if they are within the project, or absolute if they are outside the project.

        Args:
            project (Project):    The PDM project instance.
            options (Namespace):  The command line options, with a `relpaths` attribute containing the list of relative paths to set as bin directories.

        Returns:
            int: The exit code of the command. 0 indicates success, non-zero indicates failure.
        """
        relpaths: list[str] = options.relpaths
        if not isinstance(relpaths, list) or not all(isinstance(item, str) for item in relpaths):
            print(f"Invalid directory list provided to `pdm {self.cmd_name} set`: {relpaths}", file=sys.stderr)
            return 1
        relpaths = _normalize_relpaths(project, relpaths)
        if update_bin_dirs(project, relpaths):
            print(f"Bin directories set to: {relpaths}", file=sys.stderr)
        return 0
    
    def handle_add(self, project: Project, options: Namespace) -> int:
        """Handle the `pdm bin-dir add` command. Add the given list of relative paths to the configured bin directories, and write to pyproject.toml.
        
        By default, paths that resolve to the same absolute path as an existing configured directory will be ignored to avoid duplicates.
        The new paths will be appended to the end of the existing list of directories.
        
        By default, the given paths are normalized to be relative to the project root if they are within the project, or absolute if they are outside the project.

        Args:
            project (Project):    The PDM project instance.
            options (Namespace):  The command line options, with a `relpaths` attribute containing the list of relative paths to set as bin directories.

        Returns:
            int: The exit code of the command. 0 indicates success, non-zero indicates failure.
        """
        new_relpaths: list[str] = options.relpaths
        if not isinstance(new_relpaths, list) or not all(isinstance(item, str) for item in new_relpaths):
            print(f"Invalid directory list provided to `pdm {self.cmd_name} add`: {new_relpaths}", file=sys.stderr)
            return 1
        new_relpaths = _normalize_relpaths(project, new_relpaths)
        existing_abspaths = set(get_bin_dirs(project))
        new_relpaths = [relpath for relpath in new_relpaths if _get_abspath(project, relpath) not in existing_abspaths]
        new_paths = get_bin_reldirs(project) + new_relpaths
        if update_bin_dirs(project, new_paths):
            print(f"Bin directories set to: {new_paths}", file=sys.stderr)
        return 0
    
    @override
    def handle(self, project: Project, options: Namespace) -> None:
        """Handle the `pdm bin-dir` command and all subcommands.
        
        Deals with raised exceptions and prints user-friendly messages to stderr. Returns appropriate exit codes for success or failure.

        Args:
            project (Project): The PDM project instance.
            options (Namespace): The ArgParse command line options. The `BINDIR_SUBCMD` attribute indicates the subcommand
                                 if any.
        """
        retcode = 1
        try:
            subcmd_name: str | None = options.bindir_subcmd
            if subcmd_name is None or subcmd_name == "show":
                retcode = self.handle_show(project, options)
            elif subcmd_name == "set":
                retcode = self.handle_set(project, options)
            elif subcmd_name == "add":
                retcode = self.handle_add(project, options)
            else:
                raise ValueError(f"Invalid subcommand for `pdm {self.cmd_name}`: {subcmd_name!r}")
        except Exception:
            raise
        if retcode != 0:
            sys.exit(retcode)
 
def _add_bin_dirs_to_path(project: Project, **_: object) -> None:
    """Signal handler for the PDM `pre_invoke` signal.
    
    called by PDM before invoking any command.
    
    Adds the absolute form of the configured bin directories to the front of the PATH environment variable before any command is invoked.
    
    Paths that are effectively already in PATH will not be added again to avoid duplicates. The directories appear in the order they are configured.
    """
    bin_dirs = get_bin_dirs(project)
    if len(bin_dirs) == 0:
        return
    path = os.environ.get("PATH", "")
    old_dir_list = [] if len(path) == 0 else path.split(os.pathsep)
    existing_dirs = set(old_dir_list)
    new_dirs = [bin_dir for bin_dir in bin_dirs if bin_dir not in existing_dirs]
    if len(new_dirs) == 0:
        return
    new_path = os.pathsep.join(new_dirs + old_dir_list)
    os.environ["PATH"] = new_path

def plugin(core: Core) -> None:
    """PDM Plugin entry point called by PDM at startup to initialize the plugin.

    Args:
        core (Core): The PDM core instance.
    """
    pre_invoke.connect(_add_bin_dirs_to_path)
    core.register_command(BinDirCommand, BinDirCommand.cmd_name)

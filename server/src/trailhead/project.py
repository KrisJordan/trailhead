"""Project-root and project-path helpers used by the Trailhead server."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT_ENV = "TRAILHEAD_ROOT"


def get_project_root() -> Path:
    """Return the project Trailhead should inspect and run modules from.

    The CLI stores its ``--root`` value in the environment because Uvicorn's
    reload worker starts a fresh interpreter.  Falling back to the current
    directory keeps ``uvicorn trailhead.app:app`` useful outside the CLI.
    """

    configured_root = os.environ.get(PROJECT_ROOT_ENV)
    root = Path(configured_root).expanduser() if configured_root else Path.cwd()
    return root.resolve()


def set_project_root(root: str | os.PathLike[str]) -> Path:
    """Resolve and export the project root for this process and child workers."""

    resolved_root = Path(root).expanduser().resolve()
    if not resolved_root.is_dir():
        raise NotADirectoryError(f"Trailhead project root is not a directory: {root}")
    os.environ[PROJECT_ROOT_ENV] = str(resolved_root)
    return resolved_root


def module_file(module: str, root: Path | None = None) -> Path:
    """Resolve a dotted Python module name to a file inside the project root."""

    parts = module.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        raise ValueError(f"Invalid Python module name: {module!r}")

    project_root = (root or get_project_root()).resolve()
    path = project_root.joinpath(*parts).with_suffix(".py").resolve()
    if not path.is_relative_to(project_root):
        raise ValueError(f"Module is outside the project root: {module!r}")
    return path


def project_file(path: str | os.PathLike[str], root: Path | None = None) -> Path:
    """Resolve a client-provided relative path within the project root."""

    project_root = (root or get_project_root()).resolve()
    requested = Path(path)
    if requested.is_absolute():
        raise ValueError("Project paths must be relative")

    resolved = (project_root / requested).resolve()
    if not resolved.is_relative_to(project_root):
        raise ValueError("Project path is outside the project root")
    return resolved


def client_path(path: Path, root: Path | None = None) -> str:
    """Return a stable, project-relative path for the browser client.

    The client has historically expected paths to begin with ``./``.  POSIX
    separators make that API representation identical on Windows, macOS, and
    Linux.
    """

    project_root = (root or get_project_root()).resolve()
    relative = path.resolve().relative_to(project_root)
    return f"./{relative.as_posix()}"

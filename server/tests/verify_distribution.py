"""Verify that built Trailhead archives contain code and browser assets."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import sys
import tarfile
import zipfile

REQUIRED_PACKAGE_FILES = {
    "trailhead/__init__.py",
    "trailhead/__main__.py",
    "trailhead/_child_bootstrap.py",
    "trailhead/app.py",
    "trailhead/wrappers/__init__.py",
    "trailhead/wrappers/module.py",
    "trailhead/wrappers/interact/__init__.py",
    "trailhead/static/index.html",
}
DISTRIBUTION_BASENAME = "trailhead_edu"


def _wheel_entries(path: Path) -> tuple[set[str], str]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        entry_points = "\n".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".dist-info/entry_points.txt")
        )
    return names, entry_points


def _sdist_entries(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        normalized: set[str] = set()
        for name in archive.getnames():
            parts = PurePosixPath(name).parts
            if len(parts) > 1:
                normalized.add(PurePosixPath(*parts[1:]).as_posix())
        return normalized


def _check_package_entries(entries: set[str], prefix: str, label: str) -> list[str]:
    errors: list[str] = []
    expected = {f"{prefix}{name}" for name in REQUIRED_PACKAGE_FILES}
    missing = sorted(expected - entries)
    if missing:
        errors.append(f"{label} is missing: {', '.join(missing)}")

    asset_prefix = f"{prefix}trailhead/static/assets/"
    built_assets = [
        name
        for name in entries
        if name.startswith(asset_prefix)
        and not name.endswith("/")
        and not name.endswith(".gitkeep")
    ]
    if not built_assets:
        errors.append(
            f"{label} has no built files under {asset_prefix}; build the client first"
        )
    return errors


def verify(directory: Path) -> list[str]:
    errors: list[str] = []
    wheels = sorted(directory.glob(f"{DISTRIBUTION_BASENAME}-*.whl"))
    sdists = sorted(directory.glob(f"{DISTRIBUTION_BASENAME}-*.tar.gz"))
    if len(wheels) != 1:
        errors.append(
            f"expected one Trailhead wheel in {directory}, found {len(wheels)}"
        )
    if len(sdists) != 1:
        errors.append(
            f"expected one Trailhead sdist in {directory}, found {len(sdists)}"
        )

    if len(wheels) == 1:
        entries, entry_points = _wheel_entries(wheels[0])
        errors.extend(_check_package_entries(entries, "", wheels[0].name))
        if "trailhead = trailhead.__main__:main" not in entry_points:
            errors.append(f"{wheels[0].name} has no trailhead console entry point")

    if len(sdists) == 1:
        entries = _sdist_entries(sdists[0])
        errors.extend(_check_package_entries(entries, "src/", sdists[0].name))
        if "pyproject.toml" not in entries:
            errors.append(f"{sdists[0].name} is missing pyproject.toml")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error(f"archive directory does not exist: {args.directory}")

    errors = verify(args.directory)
    if errors:
        for error in errors:
            print(f"distribution verification failed: {error}", file=sys.stderr)
        return 1
    print("Trailhead wheel and source archive contain server code and browser assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

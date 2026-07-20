from __future__ import annotations

from pathlib import Path

import pytest

from trailhead.controller import list_files_async
from trailhead.models import Module, Package
from trailhead.project import client_path, module_file, project_file


def test_module_file_resolves_dotted_name_inside_root(tmp_path: Path) -> None:
    expected = tmp_path / "package" / "example.py"
    assert module_file("package.example", tmp_path) == expected


@pytest.mark.parametrize(
    "module", ["", ".example", "example.", "../example", "hello-world"]
)
def test_module_file_rejects_invalid_names(tmp_path: Path, module: str) -> None:
    with pytest.raises(ValueError):
        module_file(module, tmp_path)


def test_project_file_rejects_escape_from_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        project_file("../outside.py", tmp_path)


def test_client_path_uses_browser_separator(tmp_path: Path) -> None:
    nested = tmp_path / "package" / "example.py"
    assert client_path(nested, tmp_path) == "./package/example.py"


async def test_list_files_returns_portable_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "zebra.py").write_text('"""A zebra."""\n', encoding="utf-8")
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text('"""A package."""\n', encoding="utf-8")
    (package_dir / "caf\N{LATIN SMALL LETTER E WITH ACUTE}.py").write_text(
        '"""Unicode source: \N{SNOWMAN}."""\n', encoding="utf-8"
    )
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "hidden.py").write_text("pass\n", encoding="utf-8")

    tree = await list_files_async(tmp_path, tmp_path)

    assert [child.name for child in tree.children] == ["package", "zebra.py"]
    package = tree.children[0]
    assert isinstance(package, Package)
    assert package.full_path == "./package"
    assert package.docstring == "A package."
    assert len(package.children) == 1
    module = package.children[0]
    assert isinstance(module, Module)
    assert module.full_path == "./package/caf\N{LATIN SMALL LETTER E WITH ACUTE}.py"
    assert module.docstring == "Unicode source: \N{SNOWMAN}."

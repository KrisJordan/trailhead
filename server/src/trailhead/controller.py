import asyncio
import ast
import os
from pathlib import Path
import tokenize

from fastapi import WebSocket

from .web_socket_event import WebSocketEvent
from .async_python_subprocess import AsyncPythonSubprocess
from .models import NamespaceTree, Module, Package
from .analysis.inspect import analyze_module
from .project import client_path, get_project_root, module_file, project_file

subprocesses: dict[int, AsyncPythonSubprocess] = {}


async def web_socket_controller(client: WebSocket, event: WebSocketEvent):
    response: WebSocketEvent
    match event.type:
        case "LS":
            files = await list_files_async(get_project_root())
            response = WebSocketEvent(type="LS", data={"files": files})
        case "RUN":
            request_id = event.data["request_id"]
            module_name = event.data["module"]
            try:
                path = module_file(module_name)
            except ValueError:
                path = None
            if path is None or not path.is_file():
                response = WebSocketEvent(
                    type="ERROR",
                    data={"message": "Module not found", "request_id": request_id},
                )
            else:
                subprocess = AsyncPythonSubprocess(module_name, client)
                pid = await subprocess.start()
                subprocesses[pid] = subprocess
                response = WebSocketEvent(
                    type="RUNNING", data={"pid": pid, "request_id": request_id}
                )
        case "KILL":
            pid = event.data["pid"]
            if pid in subprocesses:
                process = subprocesses[pid]
                if process:
                    process.kill()
            return
        case "STDIN":
            pid = event.data["pid"]
            if pid in subprocesses:
                process = subprocesses[pid]
                if process:
                    await process.write(event.data["data"])
            return
        case "INSPECT":
            path = project_file(event.data["path"])
            response = WebSocketEvent(
                type="INSPECT", data=analyze_module(str(path)).model_dump()
            )
        case _:
            response = WebSocketEvent(type="??", data={})

    await client.send_text(response.model_dump_json())


def _get_docstring_by_path(path: Path) -> str:
    if not path.is_file():
        return ""
    with tokenize.open(path) as source:
        try:
            tree = ast.parse(source.read())
            return ast.get_docstring(tree) or ""
        except Exception as e:
            return f"{type(e).__name__} encountered when parsing"


_IGNORED_DIRECTORIES = {
    ".devcontainer",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "tools",
    "venv",
}


async def list_files_async(
    directory: str | os.PathLike[str], project_root: Path | None = None
) -> NamespaceTree:
    """List Python modules using stable browser paths on every host OS."""

    root = (project_root or get_project_root()).resolve()
    directory_path = Path(directory)
    if not directory_path.is_absolute():
        directory_path = root / directory_path
    directory_path = directory_path.resolve()

    if not directory_path.is_relative_to(root):
        raise ValueError("Cannot list a directory outside the project root")

    entries = await asyncio.to_thread(lambda: list(os.scandir(directory_path)))
    packages: list[Package | Module] = []
    for entry in entries:
        if entry.is_symlink():
            continue
        if (
            entry.is_file(follow_symlinks=False)
            and entry.name.endswith(".py")
            and not entry.name.startswith("__")
        ):
            entry_path = Path(entry.path)
            # If the entry is a .py file, create a Module object.
            module = Module(
                name=entry.name,
                full_path=client_path(entry_path, root),
                docstring=_get_docstring_by_path(entry_path),
            )
            packages.append(module)
        elif entry.is_dir(follow_symlinks=False):
            if entry.name in _IGNORED_DIRECTORIES:
                continue
            entry_path = Path(entry.path)
            tree = await list_files_async(entry_path, root)
            package = Package(
                children=tree.children,
                name=entry.name,
                full_path=client_path(entry_path, root),
                docstring=_get_docstring_by_path(entry_path / "__init__.py"),
            )
            packages.append(package)
    packages.sort(key=lambda item: item.name.casefold())
    return NamespaceTree(children=packages)

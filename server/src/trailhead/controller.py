import aiofiles.os
import ast
import pathlib
from fastapi import WebSocket
from .web_socket_event import WebSocketEvent
from .async_python_subprocess import AsyncPythonSubprocess
from .models import NamespaceTree, Module, Package
from .analysis.inspect import analyze_module

subprocesses: dict[int, AsyncPythonSubprocess] = {}


async def web_socket_controller(client: WebSocket, event: WebSocketEvent):
    response: WebSocketEvent
    match event.type:
        case "LS":
            files = await list_files_async(".")
            response = WebSocketEvent(type="LS", data={"files": files})
        case "RUN":
            request_id = event.data["request_id"]
            subprocess = AsyncPythonSubprocess(event.data["module"], client)
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
                    process.write(event.data["data"])
            return
        case "INSPECT":
            path = event.data["path"]
            response = WebSocketEvent(
                type="INSPECT", data=analyze_module(path).model_dump()
            )
        case _:
            response = WebSocketEvent(type="??", data={})

    await client.send_text(response.model_dump_json())


def _get_docstring_by_path(path: str) -> str:
    path_obj = pathlib.Path(path)
    if not path_obj.exists():
        return ""
    with open(path) as f:
        tree = ast.parse(f.read())
        return ast.get_docstring(tree) or ""


async def list_files_async(directory: str) -> NamespaceTree:
    packages: list[Package | Module] = []
    for entry in await aiofiles.os.scandir(directory):
        if (
            entry.is_file()
            and entry.name.endswith(".py")
            and not entry.name.startswith("__")
        ):
            # If the entry is a .py file, create a Module object.
            module = Module(
                name=entry.name,
                full_path=entry.path,
                docstring=_get_docstring_by_path(entry.path),
            )
            packages.append(module)
        elif entry.is_dir():
            if entry.name in (
                "node_modules",
                ".git",
                ".vscode",
                ".devcontainer",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                "tools",
            ):
                continue
            tree = await list_files_async(entry.path)
            package = Package(
                children=tree.children,
                name=entry.name,
                full_path=entry.path,
                docstring=_get_docstring_by_path(f"{entry.path}/__init__.py"),
            )
            packages.append(package)
    packages.sort(key=lambda o: o.name)
    return NamespaceTree(children=packages)

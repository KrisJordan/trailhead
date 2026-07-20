"""Main module for the introductory programming web server."""

__author__ = "Kris Jordan <kris@cs.unc.edu>"
__copyright__ = "Copyright 2024"
__license__ = "MIT"

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from .web_socket_manager import WebSocketManager
from .file_observer import FileObserver
from .controller import web_socket_controller
from .web_socket_event import WebSocketEvent
from .async_python_subprocess import AsyncPythonSubprocess
from .analysis.inspect import analyze_module, Module
from .project import get_project_root, module_file
from .websocket_origin import (
    WebSocketOriginMiddleware,
    configured_websocket_origins,
)

web_socket_manager = WebSocketManager(web_socket_controller)
"""Web Socket Manager handles connections and dispatches to the controller."""

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This function is called before the FastAPI web server begins, yields while
    the web server is running, then shuts down depencies when halting. It is
    responsible for starting and stopping the file observer and the web socket
    manager.
    """
    # Validate configuration at startup rather than waiting for the first
    # browser connection.  Invalid values fail closed in the middleware too.
    configured_websocket_origins()
    file_observer = FileObserver(get_project_root(), web_socket_manager.notify)
    try:
        yield
    finally:
        file_observer.stop()
        await asyncio.to_thread(file_observer.join, 5)
        await web_socket_manager.stop()


app = FastAPI(lifespan=lifespan)
"""The FastAPI web server instance."""
app.add_middleware(WebSocketOriginMiddleware)


@app.get("/api/module/{module}")
async def get_module(module: str) -> Module:
    try:
        path = module_file(module)
    except ValueError:
        raise HTTPException(status_code=404, detail="Module not found") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Module not found")
    return analyze_module(str(path))


@app.get("/api/heartbeat")
async def get_heartbeat():
    return "heartbeat"


async def _run_module_process(
    module: str, client: WebSocket, wrapper: str = "trailhead.wrappers.module"
) -> None:
    """Run a module wrapper and relay its standard streams over a WebSocket."""

    subprocess: AsyncPythonSubprocess | None = None
    await client.accept()
    try:
        path = module_file(module)
    except ValueError:
        path = None
    if path is None or not path.is_file():
        await client.close(code=1008, reason="Module not found")
        return

    try:
        subprocess = AsyncPythonSubprocess(module, client, wrapper)
        pid = await subprocess.start()
        response = WebSocketEvent(type="RUNNING", data={"pid": pid})
        await client.send_text(response.model_dump_json())
        while not subprocess.subprocess_exited():
            try:
                data = await asyncio.wait_for(client.receive_text(), timeout=0.1)
                event = WebSocketEvent.model_validate_json(data)
                match event.type:
                    case "KILL":
                        subprocess.kill()
                    case "STDIN":
                        await subprocess.write(event.data["data"])

            except asyncio.TimeoutError:
                # Expected while waiting for client input
                pass
        await subprocess.await_end()
    except WebSocketDisconnect:
        pass
    finally:
        if subprocess is not None and not subprocess.subprocess_exited():
            subprocess.kill()

        if client.client_state == WebSocketState.CONNECTED:
            await client.close()


@app.websocket("/ws/{module}/run")
async def run_module(module: str, client: WebSocket):
    """Run a Python module and relay its input and output."""

    await _run_module_process(module, client)


@app.websocket("/ws/{module}/repl")
async def repl_module(module: str, client: WebSocket):
    """Start an interactive REPL for a Python module."""

    await _run_module_process(module, client, "trailhead.wrappers.repl")


@app.websocket("/ws/{module}/repl_gui")
async def repl_gui(module: str, client: WebSocket):
    """Start the graphical REPL protocol for a Python module."""

    await _run_module_process(module, client, "trailhead.wrappers.repl_gui")


@app.websocket("/ws")
async def websocket_endpoint(client: WebSocket):
    """The FastAPI web socket endpoint dispatches out to Web Socket Manager."""
    await web_socket_manager.accept(client)


if (STATIC_DIR / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets", html=True),
        name="assets",
    )


@app.get("/{full_path:path}")
async def read_index(full_path: str):
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="Trailhead's web client has not been built or installed.",
        )
    return FileResponse(index)

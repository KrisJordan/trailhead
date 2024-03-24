"""Main module for the introductory programming web server."""

__author__ = "Kris Jordan <kris@cs.unc.edu>"
__copyright__ = "Copyright 2024"
__license__ = "MIT"

import os
import sys
import asyncio
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.concurrency import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState

from .web_socket_manager import WebSocketManager
from .file_observer import FileObserver
from .controller import web_socket_controller
from .web_socket_event import WebSocketEvent
from .async_python_subprocess import AsyncPythonSubprocess
from .analysis.inspect import analyze_module, Module

web_socket_manager = WebSocketManager(web_socket_controller)
"""Web Socket Manager handles connections and dispatches to the controller."""

# Get the path of this file
__path__ = os.path.dirname(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This function is called before the FastAPI web server begins, yields while
    the web server is running, then shuts down depencies when halting. It is
    responsible for starting and stopping the file observer and the web socket
    manager.
    """
    file_observer = FileObserver(".", web_socket_manager.notify)
    yield
    file_observer.stop()
    await web_socket_manager.stop()


app = FastAPI(lifespan=lifespan)
"""The FastAPI web server instance."""


@app.get("/api/module/{module}")
async def get_module(module: str) -> Module:
    path = module.replace(".", "/") + ".py"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Module not found")
    else:
        return analyze_module(path)


@app.get("/api/heartbeat")
async def get_heartbeat():
    return "heartbeat"


@app.websocket("/ws/{module}/run")
async def run_module(module: str, client: WebSocket):
    """The FastAPI web socket endpoint dispatches out to Web Socket Manager."""
    await client.accept()
    try:
        # Begin the async_python_subprocess
        subprocess = AsyncPythonSubprocess(module, client)
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
                        subprocess.write(event.data["data"])

            except asyncio.TimeoutError:
                # Expected while waiting for client input
                pass
        await subprocess.await_end()
    except Exception as e:
        print(e, sys.stderr)
    finally:
        if not subprocess.subprocess_exited():
            subprocess.kill()

        if client.client_state == WebSocketState.CONNECTED:
            await client.close()


@app.websocket("/ws/{module}/repl")
async def repl_module(module: str, client: WebSocket):
    """The FastAPI web socket endpoint dispatches out to Web Socket Manager."""
    await client.accept()
    try:
        # Begin the async_python_subprocess
        subprocess = AsyncPythonSubprocess(module, client, "trailhead.wrappers.repl")
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
                        subprocess.write(event.data["data"])

            except asyncio.TimeoutError:
                # Expected while waiting for client input
                pass
        await subprocess.await_end()
    except Exception as e:
        print(e, sys.stderr)
    finally:
        if not subprocess.subprocess_exited():
            subprocess.kill()

        if client.client_state == WebSocketState.CONNECTED:
            await client.close()


@app.websocket("/ws/{module}/repl_gui")
async def repl_gui(module: str, client: WebSocket):
    """The FastAPI web socket endpoint dispatches out to Web Socket Manager."""
    await client.accept()
    try:
        # Begin the async_python_subprocess
        subprocess = AsyncPythonSubprocess(
            module, client, "trailhead.wrappers.repl_gui"
        )
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
                        subprocess.write(event.data["data"])

            except asyncio.TimeoutError:
                # Expected while waiting for client input
                pass
        await subprocess.await_end()
    except Exception as e:
        print(e, sys.stderr)
    finally:
        if not subprocess.subprocess_exited():
            subprocess.kill()

        if client.client_state == WebSocketState.CONNECTED:
            await client.close()


@app.websocket("/ws")
async def websocket_endpoint(client: WebSocket):
    """The FastAPI web socket endpoint dispatches out to Web Socket Manager."""
    await web_socket_manager.accept(client)


app.mount("/assets", StaticFiles(directory=f"{__path__}/static/assets", html=True))
"""Static files are served from the static HTML directory."""


@app.get("/{full_path:path}")
async def read_index(full_path: str):
    return FileResponse(f"{__path__}/static/index.html")

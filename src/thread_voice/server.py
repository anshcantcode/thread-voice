"""Loopback-only web application; each socket owns one bounded runtime."""

import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from websockets.exceptions import WebSocketException

from . import __version__
from .live import LiveRelay
from .runtime import Runtime
from .storage import Notebook

WEB = Path(__file__).parent / "web"
app = FastAPI(title="THREAD Voice", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
active_sessions = 0


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["search", "interrupt", "draft", "confirm", "notebook", "demo", "export", "voice.start", "voice.stop", "voice.text"]
    query: str = Field(default="", max_length=500)
    title: str = Field(default="", max_length=160)
    content: str = Field(default="", max_length=8000)
    proposal_id: str = Field(default="", max_length=64)
    revision: int = Field(default=0, ge=0)
    text: str = Field(default="", max_length=4000)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
    })
    return response


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html")


@app.get("/healthz")
async def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
async def configuration():
    return {"version": __version__, "live_configured": bool(os.getenv("GEMINI_API_KEY")), "live_model": os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")}


@app.websocket("/ws")
async def workspace(socket: WebSocket):
    global active_sessions
    origin = socket.headers.get("origin")
    host = socket.headers.get("host", "")
    if (origin and origin.rstrip("/") != f"http://{host}") or active_sessions >= 8:
        await socket.close(code=1008)
        return
    active_sessions += 1
    await socket.accept()
    queue = asyncio.Queue(maxsize=256)
    notebook = Notebook(Path(os.getenv("THREAD_DATA_DIR", str(Path.home() / ".thread-voice"))) / "notes.sqlite3")
    runtime = Runtime(notebook, queue.put_nowait)
    live = LiveRelay(runtime, queue.put_nowait)
    connect_task = None

    async def send():
        while True:
            await socket.send_json(await queue.get())

    async def connect():
        try:
            await live.connect(os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live"))
        except asyncio.CancelledError:
            await live.close()
            raise
        except (OSError, ValueError, TimeoutError, WebSocketException):
            await live.close()
            runtime.emit("voice.error", message="Live connection failed. Check the server key, model access, and quota.")

    sender = asyncio.create_task(send())
    runtime.emit("session.ready", message="Local workspace ready. No microphone or model is active.")
    try:
        async with asyncio.timeout(900):
            command_count = 0
            while True:
                packet = await socket.receive()
                if packet["type"] == "websocket.disconnect":
                    break
                if data := packet.get("bytes"):
                    if len(data) > 32000 or len(data) % 2:
                        raise ValueError("invalid audio frame")
                    await live.audio(data)
                    continue
                raw = packet.get("text", "")
                command_count += 1
                if len(raw) > 16000 or command_count > 2000:
                    raise ValueError("message too large")
                try:
                    command = Command.model_validate_json(raw)
                except ValidationError:
                    runtime.emit("command.rejected", message="Unsupported or invalid command.")
                    continue
                if command.type not in ("demo", "export") and runtime.demo_task:
                    runtime.demo_task.cancel()
                if command.type == "search" and command.query.strip():
                    runtime.lookup(command.query.strip())
                elif command.type == "interrupt":
                    live.interrupt()
                    runtime.interrupt()
                elif command.type == "draft" and command.title.strip() and command.content.strip():
                    runtime.prepare_note(command.title.strip(), command.content.strip())
                elif command.type == "confirm":
                    runtime.confirm(command.proposal_id, command.revision)
                elif command.type == "notebook":
                    try:
                        runtime.emit("notebook.loaded", notes=notebook.recent())
                    except (OSError, sqlite3.Error):
                        runtime.emit("command.rejected", message="The notebook could not be read. Check the data directory.")
                elif command.type == "demo":
                    if live.socket:
                        runtime.emit("command.rejected", message="Disconnect live voice before running a scripted scenario.")
                    else:
                        runtime.run_demo()
                elif command.type == "export":
                    queue.put_nowait({"type": "session.export", "format": "thread-voice.events.v1", "events": list(runtime.events), "truncated": runtime.sequence > len(runtime.events)})
                elif command.type == "voice.start":
                    if not os.getenv("GEMINI_API_KEY"):
                        runtime.emit("voice.error", message="Set GEMINI_API_KEY on the server to enable live voice.")
                    elif live.socket or (connect_task and not connect_task.done()):
                        runtime.emit("voice.notice", message="Live voice is already connecting or connected.")
                    else:
                        connect_task = asyncio.create_task(connect())
                elif command.type == "voice.stop":
                    if connect_task and not connect_task.done():
                        connect_task.cancel()
                        await asyncio.gather(connect_task, return_exceptions=True)
                    await live.close()
                    runtime.interrupt("voice disconnected")
                    runtime.emit("voice.disconnected")
                elif command.type == "voice.text" and command.text.strip():
                    try:
                        await live.text(command.text.strip())
                    except ValueError:
                        runtime.emit("voice.error", message="Connect live voice before sending a message.")
    except (WebSocketDisconnect, TimeoutError, ValueError, asyncio.QueueFull, WebSocketException):
        pass
    finally:
        if connect_task and not connect_task.done():
            connect_task.cancel()
            await asyncio.gather(connect_task, return_exceptions=True)
        await runtime.close()
        await live.close()
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        active_sessions -= 1
        try:
            await socket.close()
        except RuntimeError:
            pass


app.mount("/static", StaticFiles(directory=WEB), name="static")

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from thread_voice.server import app


def until(socket, kind):
    for _ in range(40):
        event = socket.receive_json()
        if event["type"] == kind:
            return event
    raise AssertionError(f"Event {kind} was not received")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict("os.environ", {"THREAD_DATA_DIR": self.directory.name, "GEMINI_API_KEY": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(app)

    def test_http_surface_and_packaged_static_assets(self):
        self.assertEqual(self.client.get("/healthz").json()["status"], "ok")
        self.assertIn("Your day, in conversation.", self.client.get("/").text)
        self.assertIn('id="thread-canvas"', self.client.get("/").text)
        for name in ("app.js", "audio.js", "style.css", "galaxy.css", "workspace.css", "integration.css", "orb.js", "capture-worklet.js", "mark.svg", "fonts/Manrope.ttf", "fonts/Manrope-OFL.txt", "images/thread-sphere.png"):
            self.assertEqual(self.client.get("/static/" + name).status_code, 200)
        self.assertIn("frame-ancestors 'none'", self.client.get("/").headers["content-security-policy"])

    def test_secret_and_private_files_are_not_exposed(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "never-send-this-key"}):
            config = self.client.get("/api/config")
        self.assertNotIn("never-send-this-key", config.text)
        self.assertTrue(config.json()["live_configured"])
        for path in ("/.env", "/static/../.env", "/static/../../server.py"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_remote_host_and_cross_origin_websocket_are_rejected(self):
        self.assertEqual(self.client.get("/", headers={"host": "attacker.example"}).status_code, 400)
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/ws", headers={"origin": "https://attacker.example"}):
                pass

    def test_invalid_command_cannot_dispatch(self):
        with self.client.websocket_connect("/ws") as socket:
            until(socket, "session.ready")
            socket.send_json({"type": "draft", "title": "x", "content": "y", "save": True})
            self.assertEqual(until(socket, "command.rejected")["revision"], 0)
            socket.send_json({"type": "confirm", "revision": True})
            until(socket, "command.rejected")
        self.assertFalse((Path(self.directory.name) / "notes.sqlite3").exists())

    def test_draft_confirm_and_export_end_to_end(self):
        with self.client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as socket:
            until(socket, "session.ready")
            socket.send_json({"type": "draft", "title": "A note", "content": "User content"})
            proposal = until(socket, "draft.prepared")["proposal"]
            self.assertFalse((Path(self.directory.name) / "notes.sqlite3").exists())
            socket.send_json({"type": "confirm", "proposal_id": proposal["id"], "revision": proposal["revision"]})
            receipt = until(socket, "note.receipt")
            self.assertEqual(receipt["receipt"]["content"], "User content")
            socket.send_json({"type": "export"})
            exported = until(socket, "session.export")
            self.assertFalse(exported["truncated"])
            self.assertEqual(exported["format"], "thread-voice.events.v1")
            self.assertNotIn("audio/pcm", json.dumps(exported))
            socket.send_json({"type": "notebook"})
            self.assertEqual(until(socket, "notebook.loaded")["notes"][0]["content"], "User content")

    def test_missing_voice_key_fails_without_connecting_provider(self):
        with self.client.websocket_connect("/ws") as socket:
            until(socket, "session.ready")
            with patch("thread_voice.live.websockets.connect") as upstream:
                socket.send_json({"type": "voice.start"})
                self.assertIn("GEMINI_API_KEY", until(socket, "voice.error")["message"])
                upstream.assert_not_called()

    def test_interrupted_proposal_cannot_be_saved_over_transport(self):
        with self.client.websocket_connect("/ws") as socket:
            until(socket, "session.ready")
            socket.send_json({"type": "draft", "title": "Old", "content": "Must expire"})
            proposal = until(socket, "draft.prepared")["proposal"]
            socket.send_json({"type": "interrupt"})
            until(socket, "playback.clear")
            socket.send_json({"type": "confirm", "proposal_id": proposal["id"], "revision": proposal["revision"]})
            until(socket, "confirmation.rejected")
        self.assertFalse((Path(self.directory.name) / "notes.sqlite3").exists())

    def test_oversized_and_odd_audio_frames_close_socket(self):
        for frame in (b"x", b"x" * 32002):
            with self.client.websocket_connect("/ws") as socket:
                until(socket, "session.ready")
                socket.send_bytes(frame)
                with self.assertRaises(WebSocketDisconnect):
                    socket.receive_json()

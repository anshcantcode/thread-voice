import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from thread_voice.live import LiveRelay, TOOLS
from thread_voice.runtime import Runtime
from thread_voice.storage import Notebook


class Upstream:
    def __init__(self):
        self.sent = []
        self.messages = asyncio.Queue()
        self.messages.put_nowait(json.dumps({"setupComplete": {}}))
        self.closed = False
    async def send(self, value):
        self.sent.append(json.loads(value))
    async def recv(self):
        return await self.messages.get()
    def __aiter__(self):
        return self
    async def __anext__(self):
        return await self.messages.get()
    async def close(self):
        self.closed = True


class LiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.events, self.frames = [], []
        self.runtime = Runtime(Notebook(Path(self.directory.name) / "notes.sqlite3"), self.events.append)
        self.relay = LiveRelay(self.runtime, self.frames.append)
        self.upstream = Upstream()
        self.connect = patch("thread_voice.live.websockets.connect", AsyncMock(return_value=self.upstream))
        self.mock_connect = self.connect.start()
        self.addCleanup(self.connect.stop)

    async def asyncTearDown(self):
        await self.runtime.close()
        await self.relay.close()

    async def flush(self):
        for _ in range(10):
            await asyncio.sleep(0)

    async def test_key_uses_server_header_and_no_write_tool_is_declared(self):
        await self.relay.connect("private-test-key", "test-model")
        args, kwargs = self.mock_connect.call_args
        self.assertNotIn("private-test-key", args[0])
        self.assertEqual(kwargs["additional_headers"]["x-goog-api-key"], "private-test-key")
        names = [tool["name"] for tool in TOOLS[0]["functionDeclarations"]]
        self.assertEqual(names, ["search_docs", "prepare_note"])
        self.assertNotIn("private-test-key", json.dumps(self.events))

    async def test_raw_audio_is_forwarded_but_not_logged(self):
        await self.relay.audio(b"\0\0")
        self.assertFalse(self.upstream.sent)
        await self.relay.connect("key", "model")
        await self.relay.audio(b"\x01\x02")
        self.assertEqual(self.upstream.sent[-1]["realtimeInput"]["audio"]["data"], "AQI=")
        self.assertNotIn("AQI=", json.dumps(self.events))

    async def test_interruption_suppresses_old_audio_until_turn_boundary(self):
        await self.relay.connect("key", "model")
        audio = {"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": "AAAA"}}]}}}
        self.relay.turn_active = True
        self.relay.interrupt()
        self.upstream.messages.put_nowait(json.dumps(audio))
        await self.flush()
        self.assertFalse(self.frames)
        self.upstream.messages.put_nowait(json.dumps({"serverContent": {"turnComplete": True}}))
        self.upstream.messages.put_nowait(json.dumps(audio))
        await self.flush()
        self.assertEqual(len(self.frames), 1)

    async def test_first_user_speech_does_not_suppress_a_fresh_reply(self):
        await self.relay.connect("key", "model")
        self.relay.interrupt()
        self.assertFalse(self.relay.suppress_audio)
        await self.relay.text("Hello")
        self.assertFalse(self.relay.suppress_audio)
        self.relay.turn_active = True
        await self.relay.text("Actually, change direction")
        self.assertTrue(self.relay.suppress_audio)

    async def test_model_draft_requires_visible_confirmation(self):
        await self.relay.connect("key", "model")
        await self.relay.run_tool({"id": "call-1", "name": "prepare_note", "args": {"title": "Proposed", "content": "Not saved"}})
        response = self.upstream.sent[-1]["toolResponse"]["functionResponses"][0]
        self.assertEqual(response["response"]["status"], "requires_visible_confirmation")
        self.assertFalse(self.runtime.notebook.path.exists())

    async def test_unknown_tool_and_invalid_arguments_cannot_write(self):
        await self.relay.connect("key", "model")
        for name, args, status in (("save_note", {}, "unsupported_tool"), ("prepare_note", {"title": "x", "content": "y", "path": "private"}, "invalid_arguments")):
            await self.relay.run_tool({"id": name, "name": name, "args": args})
            self.assertEqual(self.upstream.sent[-1]["toolResponse"]["functionResponses"][0]["response"]["status"], status)
        self.assertFalse(self.runtime.notebook.path.exists())

    async def test_provider_interruption_expires_current_draft(self):
        await self.relay.connect("key", "model")
        proposal = self.runtime.prepare_note("Old", "Draft")
        self.upstream.messages.put_nowait(json.dumps({"serverContent": {"interrupted": True}}))
        await self.flush()
        self.runtime.confirm(proposal["id"], proposal["revision"])
        self.assertEqual(self.events[-1]["type"], "confirmation.rejected")

    async def test_closed_provider_releases_socket_and_authority(self):
        await self.relay.connect("key", "model")
        await self.relay.close()
        self.assertFalse(self.relay.ready)
        self.assertIsNone(self.relay.socket)
        self.assertTrue(self.upstream.closed)

"""Session-owned state. Providers propose; this runtime decides what can publish.

Cancellation requests save work. Revision checks provide correctness even when
a tool ignores cancellation or its response arrives after a newer request.
"""

import asyncio
from collections import deque
from copy import deepcopy
import time
import sqlite3
from uuid import uuid4

from .storage import Notebook


DOCUMENTS = (
    {"id": "barge-in", "title": "Interrupting a spoken reply", "text": "Barge-in stops scheduled audio locally. The provider receives fresh microphone audio while obsolete tool results are fenced by revision. Headphones reduce echo-induced false interruptions."},
    {"id": "revisions", "title": "Rejecting stale tool results", "text": "Every new request advances the session revision. A lookup captures its starting revision. A result can publish only when that revision is still current, even if cancellation was ignored."},
    {"id": "confirmation", "title": "Confirming a note save", "text": "A model can prepare a draft but cannot save it. Saving requires the visible confirmation control with the exact proposal ID and revision. New speech or a new request expires pending confirmation."},
    {"id": "receipts", "title": "Keeping actual outcomes", "text": "A saved note produces a durable SQLite receipt. Retrying the same proposal ID returns the same note. An interruption after a committed save cannot undo that write."},
    {"id": "privacy", "title": "Where your voice goes", "text": "The interruption lab runs locally without a model. Optional live mode sends microphone PCM and typed messages to Google Gemini. API credentials stay on the server; raw audio is never written to the event log."},
    {"id": "limits", "title": "What the lab measures", "text": "Scripted scenarios exercise real cancellation and revision logic with controlled tool delays. Their timings measure software events, not microphone-to-speaker latency or model understanding."},
)


async def search_documents(query: str) -> list[dict]:
    # A visible delay makes cancellation observable; this is an in-process search.
    await asyncio.sleep(1.2)
    words = set(query.casefold().split())
    ranked = sorted(DOCUMENTS, key=lambda doc: -sum(word in (doc["title"] + " " + doc["text"]).casefold() for word in words))
    return [dict(doc) for doc in ranked[:3]]


class Runtime:
    def __init__(self, notebook: Notebook, publish, *, search=search_documents):
        self.notebook, self.publish, self.search = notebook, publish, search
        self.revision = 0
        self.events = deque(maxlen=500)
        self.sequence = 0
        self.started = time.perf_counter()
        self.tasks: set[asyncio.Task] = set()
        self.proposal = None
        self.receipts: dict[str, dict] = {}
        self.closed = False
        self.demo_task = None
        self.demo_count = 0

    def emit(self, kind: str, **data):
        self.sequence += 1
        event = {"type": kind, "seq": self.sequence, "at_ms": round((time.perf_counter() - self.started) * 1000, 2), "revision": self.revision, **deepcopy(data)}
        self.events.append(event)
        if not self.closed:
            self.publish(event)
        return event

    def advance(self, reason: str):
        self.revision += 1
        for task in list(self.tasks):
            task.cancel()
        if self.proposal:
            self.emit("draft.expired", proposal_id=self.proposal["id"], reason=reason)
        self.proposal = None
        self.emit("revision.changed", reason=reason)

    def interrupt(self, reason="user interruption"):
        self.advance(reason)
        self.emit("playback.clear", reason=reason)

    def lookup(self, query: str):
        self.advance("new search")
        revision = self.revision
        call_id = uuid4().hex
        self.emit("search.started", query=query, call_id=call_id)
        task = asyncio.create_task(self._lookup(query, revision, call_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def _lookup(self, query, revision, call_id):
        try:
            results = await self.search(query)
        except asyncio.CancelledError:
            if not self.closed:
                self.emit("search.cancelled", call_id=call_id, query=query, started_revision=revision)
            return {"status": "cancelled"}
        except Exception:
            if not self.closed:
                self.emit("search.failed", call_id=call_id, message="The local lookup failed. Try again.")
            return {"status": "failed"}
        if self.closed:
            return {"status": "closed"}
        if revision != self.revision:
            self.emit("search.stale", call_id=call_id, started_revision=revision, query=query)
            return {"status": "superseded"}
        self.emit("search.completed", call_id=call_id, query=query, results=results)
        return {"status": "completed", "results": results}

    def prepare_note(self, title: str, content: str):
        self.advance("new draft")
        self.proposal = {"id": uuid4().hex, "revision": self.revision, "title": title, "content": content}
        self.emit("draft.prepared", proposal=self.proposal)
        return deepcopy(self.proposal)

    def confirm(self, proposal_id: str, revision: int):
        # Repeat delivery returns the existing outcome; it never executes a new save.
        if proposal_id in self.receipts:
            self.emit("note.receipt", receipt=self.receipts[proposal_id], duplicate=True)
            return
        if not self.proposal or self.proposal["id"] != proposal_id or self.proposal["revision"] != revision or revision != self.revision:
            self.emit("confirmation.rejected", message="This draft has expired. Prepare a fresh draft before saving.")
            return
        try:
            receipt = self.notebook.save(self.proposal)
        except (OSError, sqlite3.Error):
            self.emit("note.failed", message="The notebook could not save this draft. Check the data directory and retry.")
            return
        self.receipts[proposal_id] = receipt
        self.proposal = None
        self.emit("note.receipt", receipt=receipt, duplicate=False)

    def run_demo(self):
        if self.demo_task and not self.demo_task.done():
            return
        self.demo_count += 1
        self.demo_task = asyncio.create_task(self._demo())

    async def _demo(self):
        self.emit("demo.started", mode="scripted", message="Scripted input; real runtime. No model or microphone.")
        self.lookup("interrupting a spoken reply")
        await asyncio.sleep(.35)
        self.interrupt("scripted correction")
        await self.lookup("rejecting stale tool results")
        self.prepare_note("Interruption design", "Cancel obsolete reads, fence late results by revision, and require confirmation before a persistent write.")
        self.emit("demo.finished", message="Correction applied. A draft is ready for your explicit confirmation.")

    async def close(self):
        self.closed = True
        tasks = [*self.tasks, *([self.demo_task] if self.demo_task else [])]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

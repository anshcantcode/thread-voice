import asyncio
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from thread_voice.runtime import Runtime, search_documents
from thread_voice.storage import Notebook


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "notes.sqlite3"
        self.events = []
        self.runtime = Runtime(Notebook(self.path), self.events.append)

    async def asyncTearDown(self):
        await self.runtime.close()

    def kinds(self):
        return [event["type"] for event in self.events]

    async def test_late_uncancellable_read_is_excluded(self):
        started, finish = asyncio.Event(), asyncio.Event()

        async def uncooperative(query):
            if query == "old":
                started.set()
                try:
                    await finish.wait()
                except asyncio.CancelledError:
                    await finish.wait()
            return [{"title": query}]

        self.runtime.search = uncooperative
        old = self.runtime.lookup("old")
        await started.wait()
        new = self.runtime.lookup("new")
        await new
        finish.set()
        await old
        published = [event for event in self.events if event["type"] == "search.completed"]
        self.assertEqual([event["query"] for event in published], ["new"])
        self.assertIn("search.stale", self.kinds())

    async def test_interruption_cancels_cooperative_read(self):
        task = self.runtime.lookup("privacy")
        await asyncio.sleep(0)
        self.runtime.interrupt()
        await task
        self.assertIn("search.cancelled", self.kinds())
        self.assertNotIn("search.completed", self.kinds())

    async def test_interruption_expires_write_authority(self):
        proposal = self.runtime.prepare_note("Title", "Content")
        self.runtime.interrupt()
        self.runtime.confirm(proposal["id"], proposal["revision"])
        self.assertIn("confirmation.rejected", self.kinds())
        self.assertFalse(self.path.exists())

    async def test_confirmation_matches_id_and_revision(self):
        proposal = self.runtime.prepare_note("Title", "Content")
        self.runtime.confirm("different", proposal["revision"])
        self.runtime.confirm(proposal["id"], proposal["revision"] + 1)
        self.assertEqual(self.kinds().count("confirmation.rejected"), 2)
        self.assertFalse(self.path.exists())

    async def test_duplicate_delivery_and_later_interrupt_keep_one_receipt(self):
        proposal = self.runtime.prepare_note("Title", "Text with ' quotes; DROP TABLE notes;")
        self.runtime.confirm(proposal["id"], proposal["revision"])
        self.runtime.interrupt()
        self.runtime.confirm(proposal["id"], proposal["revision"])
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM notes").fetchone()[0], 1)
        receipts = [event for event in self.events if event["type"] == "note.receipt"]
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0]["receipt"], receipts[1]["receipt"])
        self.assertTrue(receipts[1]["duplicate"])

    async def test_notebook_idempotency_survives_a_new_instance(self):
        proposal = self.runtime.prepare_note("Persisted", "One note")
        first = self.runtime.notebook.save(proposal)
        self.assertEqual(Notebook(self.path).save(proposal), first)
        self.assertEqual(Notebook(self.path).recent(), [first])

    async def test_new_draft_retires_previous_draft(self):
        old = self.runtime.prepare_note("Old", "First")
        new = self.runtime.prepare_note("New", "Second")
        self.runtime.confirm(old["id"], old["revision"])
        self.assertFalse(self.path.exists())
        self.runtime.confirm(new["id"], new["revision"])
        self.assertEqual(list(self.runtime.receipts.values())[0]["title"], "New")

    async def test_failed_save_does_not_claim_success_and_can_retry(self):
        proposal = self.runtime.prepare_note("Retry", "Content")
        notebook = self.runtime.notebook
        class Broken:
            def save(self, _):
                raise sqlite3.OperationalError("private path must not be exposed")
        self.runtime.notebook = Broken()
        self.runtime.confirm(proposal["id"], proposal["revision"])
        self.assertIn("note.failed", self.kinds())
        self.assertNotIn("note.receipt", self.kinds())
        self.assertNotIn("private path", str(self.events))
        self.runtime.notebook = notebook
        self.runtime.confirm(proposal["id"], proposal["revision"])
        self.assertIn("note.receipt", self.kinds())

    async def test_trace_is_bounded_and_event_ids_are_monotonic(self):
        for i in range(550):
            self.runtime.emit("test", index=i)
        self.assertEqual(len(self.runtime.events), 500)
        self.assertEqual(self.runtime.events[0]["seq"], 51)
        self.assertEqual(self.runtime.events[-1]["seq"], 550)

    async def test_close_releases_pending_read_without_publishing(self):
        task = self.runtime.lookup("privacy")
        await asyncio.sleep(0)
        count = len(self.events)
        await self.runtime.close()
        self.assertTrue(task.done())
        self.assertEqual(len(self.events), count)

    async def test_scripted_demo_uses_real_transitions_without_saving(self):
        self.runtime.run_demo()
        await self.runtime.demo_task
        self.assertIn("search.cancelled", self.kinds())
        self.assertIn("search.completed", self.kinds())
        self.assertIn("draft.prepared", self.kinds())
        self.assertIn("demo.finished", self.kinds())
        self.assertFalse(self.path.exists())

    async def test_user_interrupt_during_demo_cannot_prepare_a_ghost_draft(self):
        self.runtime.run_demo()
        async with asyncio.timeout(2):
            while sum(event["type"] == "search.started" for event in self.events) < 2:
                await asyncio.sleep(.005)
        self.runtime.interrupt("real user correction")
        await asyncio.gather(self.runtime.demo_task, return_exceptions=True)
        await asyncio.gather(*list(self.runtime.tasks), return_exceptions=True)
        self.assertNotIn("draft.prepared", self.kinds())
        self.assertNotIn("demo.finished", self.kinds())

    async def test_search_does_not_invent_matches_for_unknown_keywords(self):
        self.assertEqual(await search_documents("xyzzy-unmatched-741"), [])

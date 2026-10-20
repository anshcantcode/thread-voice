# Workspace protocol

One WebSocket at `/ws` owns one ephemeral runtime. JSON commands and raw little-endian mono 16 kHz PCM frames share the socket. Audio is accepted only while the optional provider is connected. JSON messages are limited to 16,000 characters; audio frames to 32,000 bytes and an even byte count. Commands reject undeclared properties and invalid types.

| Client command | Fields | Behavior |
|---|---|---|
| `search` | `query` (1–500 characters) | Search bundled documents; advance revision |
| `interrupt` | none | Clear playback, cancel reads, expire draft |
| `draft` | `title` (1–160), `content` (1–8,000) | Prepare a proposal without saving |
| `confirm` | `proposal_id`, `revision` | Save only the matching current proposal, or return a prior receipt |
| `notebook` | none | Read the latest 50 saved notes from this computer |
| `demo` | none | Run the scripted local interruption scenario |
| `export` | none | Return latest 500 events as `session.export` |
| `voice.start` | none | Connect the server-configured Gemini model |
| `voice.text` | `text` (1–4,000) | Submit a live typed turn |
| `voice.stop` | none | Close provider connection and expire pending work |

Most server events contain `type`, monotonic `seq`, elapsed `at_ms`, and current `revision`. `search.stale` additionally identifies `started_revision`. Audio messages are transient `{ "type": "voice.audio", "data": "base64 PCM" }` and have no event sequence or persisted trace entry.

```json
{"type":"draft","title":"Design choice","content":"Fence tool results by revision."}
```

The response `draft.prepared` includes the proposal's random ID and revision. The confirmation must echo both. Guessing a revision, reusing a superseded draft, or sending the model's acknowledgment does not create a note. The model is never given a tool that can send this confirmation.

Trace exports use `thread-voice.events.v1` and set `truncated: true` when older events fell out of the bounded log. A trace is evidence, not an executable command stream. Receipt timestamps are UTC. Event elapsed times measure software processing within one session, not end-to-end acoustic latency.

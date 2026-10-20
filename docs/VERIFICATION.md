# Verification — v0.1.0

Recorded on **20 October 2026**. This record concerns the independently implemented THREAD Voice source, not the predecessor's benchmark or mobile releases.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | **29 passed**, Windows, Python 3.13 |
| `node tests/audio.test.mjs` | Passed on Node 22.16.0: 16/44.1/48 kHz frame conversion, owned playback cancellation, queue bounds, microphone permission/stop race |
| `python -m build --wheel` | Universal Python wheel produced |
| Wheel-content validation | All six web assets included; no environment file or notebook database included |
| Browser scenario | Actual local runtime accepted scripted inputs, cancelled obsolete search, published current results, and prepared an unsaved draft |
| Browser save and interruption | Save created a SQLite receipt; a later interruption expired a fresh draft and removed the save control |
| Persistence across restart | Saved notebook entry remained readable after restarting the server and reconnecting the browser |
| Credential boundary | Fake key absent from public configuration and runtime events; provider key supplied through a server-side header |

GitHub Actions runs the same verification script on Ubuntu and Windows with Python 3.11 and 3.13. The [workflow page](https://github.com/anshcantcode/thread-voice/actions/workflows/verify.yml) is the authority for those hosted results; defining a matrix is not evidence that every job passed.

## What the checks establish

The adversarial read catches cancellation and returns late. Its result is excluded after a newer revision. Confirmation checks reject mismatched IDs and revisions, expire on interruption, and retain one committed note across duplicate delivery. A new Notebook instance reads the same durable record. An intentional storage failure emits failure without claiming success, then permits a fresh retry.

Provider tests use an in-memory WebSocket fake. They check setup, tool boundaries, PCM forwarding, transcript-safe logging, playback suppression across turn boundaries, draft expiration and connection cleanup. They make no Google requests. The browser walkthrough uses the local lab and a synthetic note, not an actual microphone or paid model.

The initial local verification exposed SQLite handles left open by transaction-only context managers on Windows. Explicit connection closing fixed the defect. A malformed three-byte synthetic PCM fixture was corrected to an even-length valid sample; the invalid-frame regression remains in the suite. These were repaired before publication.

Final review also added a regression for user interruption while the scripted scenario awaits a cancellable read. Shielding the scenario's await prevents a child's cancellation handler from swallowing parent cancellation and preparing a draft after the user has interrupted.

## Unqualified or not run

- Paid/live Gemini session, model access, live function calling and provider quota.
- Acoustic microphone-to-speaker timing, noisy-room performance, semantic interruption recovery and speech-recognition quality.
- Mobile-device qualification and multi-user public hosting.
- Docker execution on this machine, which has no Docker CLI available. The Dockerfile and loopback-published run command are supplied for reproduction.

The energy threshold's 60 ms sample window is configuration, not measured latency. No benchmark score, production-readiness rating, or predecessor result is claimed for this release.

# Roadmap and release boundaries

## v0.1 — inspectable local runtime

Current scope: cancellation, revision-fenced reads, visible draft confirmation, durable note receipts, a keyless scenario, optional Gemini native audio, portable packaging, browser audio checks, and Windows/Linux CI. These features have different qualification levels; see [verification](VERIFICATION.md).

## Before a live-reliability claim

- Run a user-authorized, budgeted Gemini session with the exact published model/version and record its actual trace.
- Exercise corrections during tool execution, noise-triggered interruptions, microphone denial, provider disconnects, and reconnects on target browsers.
- Measure physical microphone-to-speaker interruption time with repeatable loopback equipment, recording sample counts and percentiles.
- Add false-interruption recovery only after the acoustic evidence identifies the needed behavior.

## If demand justifies a broader product

Add a second real read integration with a documented result contract; add workspace retrieval with explicit folder consent; evaluate a local speech adapter. Keep remote write integrations out until their outcome reconciliation can survive restarts and ambiguous provider responses. Authentication and deployment hardening precede any public hosted service.

No external launch, benchmark score, trained foundation model, enterprise readiness, or future integration is implied by this roadmap.

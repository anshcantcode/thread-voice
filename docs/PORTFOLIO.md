# Portfolio presentation

## Project description

**THREAD Voice — an inspectable, interruptible voice workspace.** A Python/WebSocket runtime separates model proposals from execution, cancels obsolete searches, fences late results by revision, and requires visible confirmation before idempotent SQLite writes. A dependency-free browser client provides streaming PCM, owned playback cancellation, and an exportable event timeline.

## CV bullets grounded in this release

- Designed a session-scoped asynchronous agent runtime with revision-fenced tool results, cancellation, and proposal-bound confirmation for persistent actions.
- Built a browser voice pipeline using AudioWorklet, 16 kHz PCM streaming, 24 kHz playback, local interruption detection, and an optional server-side Gemini Live adapter.
- Added a keyless interactive failure scenario and adversarial checks covering late tool responses, duplicate confirmation, expired write authority, origin validation, and microphone cleanup.

Use the published verification record for exact test counts. Do not add measured latency, user adoption, production scale, speech-recognition accuracy, or benchmark-score claims unless you have corresponding measurements. Describe the earlier hackathon as a team project and this successor as independently implemented with AI coding assistance.

## A two-minute technical walkthrough

1. Launch the keyless lab and run the scenario. Point out the obsolete search cancellation and newer revision.
2. Inspect the draft, interrupt, and show that the save control disappears. Prepare a new draft and confirm it to obtain a real receipt.
3. Export the trace and explain the separation between a proposed action and a committed outcome.
4. Show the uncooperative-tool regression: even if cancellation is ignored, the old result cannot publish.
5. Explain live-mode qualification honestly: a protocol-tested adapter exists; paid live and physical acoustic measurements are separate release gates.

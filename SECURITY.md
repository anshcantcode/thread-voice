# Security and privacy

THREAD Voice is an early, single-user application designed for a loopback connection. The launcher binds `127.0.0.1`. Docker should publish its port on `127.0.0.1` as shown in the README. There is no account authentication. Do not expose it to the internet or an untrusted local network.

HTTP host validation, exact WebSocket origin checking, strict command validation, bounded sessions and messages, a restrictive content security policy, and DOM text rendering protect the intended local boundary. This is not an OS sandbox or a complete multi-tenant threat model.

- Gemini credentials are read by the server from the environment. `/api/config` returns only version, model name and a configured flag. The browser receives no key.
- Live mode sends microphone PCM and typed conversation to Google. Provider terms, retention and charges apply separately. The keyless lab performs no model inference.
- The model can search reference documents and prepare a draft. It has no persistent-write function. Saving requires the visible current-proposal confirmation.
- SQLite lives in `~/.thread-voice`, or `THREAD_DATA_DIR`. It contains notes in plaintext under your operating-system account. It is not encrypted by the application.
- Conversation history and note content can appear in JSON exports. Inspect an export before sharing it. The runtime does not write raw microphone audio.
- Disconnecting clears conversation authority. Saved notes stay on disk until you remove your notebook database. Closing the server does not delete them.

For a potential vulnerability, use [GitHub private vulnerability reporting](https://github.com/anshcantcode/thread-voice/security/advisories/new) if enabled. Otherwise open a minimal issue asking for a private contact channel, without including exploit details, credentials, recordings or personal notes.

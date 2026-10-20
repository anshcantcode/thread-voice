# Contributing

Ansh maintains write access. Everyone can propose changes through pull requests.

Install Python 3.11+ and Node 22+, create a virtual environment, then run:

```bash
python -m pip install -e '.[dev]'
python scripts/verify.py
```

Start the workspace with `thread-voice`. An API key is unnecessary for normal development. Tests use a fake provider; do not add paid calls to the default suite. Run real provider checks only with the user's explicit finite spending authorization.

Create a branch, describe the observable problem, and keep each change focused. Include the smallest regression that demonstrates a changed boundary. Preserve stale-result fencing, exact draft confirmation, idempotent writes, actual outcome receipts, and microphone cleanup. A model's claim is not evidence that a tool executed.

Use standard-library features and the existing runtime before adding dependencies or provider abstractions. Keep data sources and model-generated text labelled. Do not publish keys, notebook contents, microphone recordings or generated environment files. Update protocol and architecture docs when the contract changes.

For bug reports include operating system, browser, package version, reproduction steps, expected and observed behavior, and a redacted event trace if useful. Distinguish synthetic checks from real microphone observations. Current verification belongs to the tested source, not an earlier project or model.

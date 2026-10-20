# Working on THREAD Voice

Read README.md and docs/ARCHITECTURE.md. Keep the project scoped to one local user and the visible runtime contracts. Never copy team assets or historical benchmark claims from the predecessor; ORIGINS.md records the relationship.

Use `python scripts/verify.py` for the local gate. Default checks must not call paid providers. Real hosted spending needs explicit finite authorization. Keep credentials, notes, audio and private traces out of commits.

Preserve cancellation plus revision fencing, proposal-bound confirmation, idempotent SQLite saves, actual outcome receipts, and microphone cleanup. Test changed boundaries without weakening existing checks. Report live and acoustic checks separately from synthetic protocol checks.

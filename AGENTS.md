# Working on THREAD Voice

Read README.md and docs/ARCHITECTURE.md. Keep the project scoped to one local user and the visible runtime contracts. Preserve the original THREAD frontend: its blue acoustic orb, typography, full-screen conversation layout, compact call dock and dark workspace were restored at the owner's request. Improve engineering without replacing that design with a developer dashboard. Keep inherited frontend attribution in ORIGINS.md and THIRD_PARTY_NOTICES.md; historical benchmark claims do not transfer.

Use `python scripts/verify.py` for the local gate. Default checks must not call paid providers. Real hosted spending needs explicit finite authorization. Keep credentials, notes, audio and private traces out of commits.

Preserve cancellation plus revision fencing, proposal-bound confirmation, idempotent SQLite saves, actual outcome receipts, and microphone cleanup. Test changed boundaries without weakening existing checks. Report live and acoustic checks separately from synthetic protocol checks.

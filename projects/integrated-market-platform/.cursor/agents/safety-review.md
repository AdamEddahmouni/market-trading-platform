---
name: imp-safety-review
description: Review IMP changes for risk authority, execution controls, mode isolation, account identity, temporal semantics, persistence, and secrets.
model_tier: high_reasoning
---

Inspect the full diff and authoritative safety docs. Treat Demo/Paper/Live
separation, `PAPER_ONLY`, risk authority, Workspace submit boundary,
`LIVE-001`, source-time/PIT behavior, append-only persistence, account
isolation, and credential redaction as hard invariants. Review backend
enforcement before frontend gates. Run the relevant invariant selectors and
return severity-ranked findings. Safety review is serial with implementation.

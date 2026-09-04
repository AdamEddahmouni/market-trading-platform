# BUILD 26 Known Limitations Register

## KL-026-001 — Minimum forward sample not yet accumulated

- **Scope:** Forward qualification evidence
- **Why it exists:** BUILD 26 infrastructure can complete before sufficient live forward observations accumulate
- **Risk:** Disposition may be `INSUFFICIENT_FORWARD_EVIDENCE`
- **Mitigation:** Fixture lifecycle proves temporal integrity; live accumulation continues separately
- **Blocking:** no

## KL-026-002 — Real Moomoo session may be unavailable locally

- **Scope:** Provider plane
- **Why it exists:** OpenD requires local broker gateway and credentials
- **Risk:** Provider matrix records `CONFIGURED_NOT_AVAILABLE` or `NOT_CONFIGURED`
- **Mitigation:** Fixture replay qualification path; bounded smoke when available
- **Blocking:** no

## KL-026-003 — IBKR observational path not primary

- **Scope:** Provider plane
- **Why it exists:** IBKR gateway not required for BUILD 26 core
- **Risk:** Cross-provider diagnostics limited
- **Mitigation:** Moomoo primary; IBKR recorded as optional
- **Blocking:** no

## KL-026-004 — Finviz Elite not required

- **Scope:** Discovery/context
- **Why it exists:** Forward market-data qualification uses trade/quote providers
- **Risk:** `FINVIZ_ELITE_NOT_CONFIGURED` when token absent
- **Mitigation:** Non-blocking for forecast qualification
- **Blocking:** no

## KL-026-005 — Production FINAL champion may abstain

- **Scope:** Intelligence plane BUILD 14
- **Why it exists:** Inherited BUILD 25 KL-004
- **Risk:** Qualification uses `QUALIFICATION_SHADOW` frozen artifact scope
- **Mitigation:** Explicit nonproduction provenance in spec
- **Blocking:** no

## KL-026-006 — BUILD 25 RC file-hash manifest excludes BUILD 26 files

- **Scope:** Reproducibility
- **Why it exists:** BUILD 25 freeze predates BUILD 26 orchestration code
- **Risk:** RC hash check validates frozen BUILD 25 scientific files only
- **Mitigation:** `release_candidate_ref` binds exact BUILD 25 HEAD in spec/run
- **Blocking:** no

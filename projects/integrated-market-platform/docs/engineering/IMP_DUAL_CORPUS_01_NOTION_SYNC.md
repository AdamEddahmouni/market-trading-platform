# IMP program status — Notion sync summary (repo)

**Purpose:** Operator-facing snapshot for Notion or program dashboards. Repo authority remains [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).

| Field | Value |
| --- | --- |
| **CURRENT_MAIN** (`origin/main` mutable tip) | `a1b556f89c8e68e84fe7246c6e726359f3a0ebf8` (IMP-EVIDENCE-HARDENING-02 software [#248](https://github.com/AdamEddahmouni/market-trading-platform/pull/248)–[#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252); tip [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)) |
| **CURRENT_SOFTWARE_IMPLEMENTATION** | `a1b556f89c8e68e84fe7246c6e726359f3a0ebf8` — last software merge [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251) Item 9 `next-rth-preflight`. Docs-only merges do **not** advance this field. |
| **ITEM9_FROZEN_COLLECTOR** | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` — governed `.imp-actual-01-phase-d/`; do not retarget prospective collection to **CURRENT_MAIN** |
| **SEP15_FROZEN_EMPIRICAL_AUTHORITY** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` — historical pin; do not rewrite |
| Last verified | 2026-09-17 |

## Program truths (do not soften)

- **Item 9:** `ITEM9_CALIBRATED` = **NO**; `ITEM9_RESULT` = **`INSUFFICIENT_CALIBRATION_EVIDENCE`**; `ITEM9_DISTINCT_RTH_DATES` = **1** / **3** (do not assume a second date). Floors: **20** observations, **3** distinct US cash RTH dates, **5** evaluation rows. Sep 17 `PATH_PROOF_ONLY` receipt immutable.
- **Item 7:** `ITEM7_STATE` = **`ITEM7_PENDING_NATURAL_EVIDENCE`**; `ITEM7_PRODUCTION_FORECAST_ARTIFACT_READY` = **NO**; governed rows **0**.
- **FTEP:** `FTEP_EMPIRICAL_ACTIVE` = **NO**; empirical locks **0**.
- **Live:** `LIVE_EXECUTION` = **OFF**.
- **Providers:** Moomoo OpenD / IBKR live = **`PROVIDER_UNVERIFIED`** (no `PROVIDER_VERIFIED` claims).
- **PR #222:** Item 7 natural settlement — **still isolated** (not merged).
- **Dual-corpus + hardening:** [#242](https://github.com/AdamEddahmouni/market-trading-platform/pull/242)–[#246](https://github.com/AdamEddahmouni/market-trading-platform/pull/246) dual-corpus software; [#248](https://github.com/AdamEddahmouni/market-trading-platform/pull/248)–[#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252) evidence hardening. `HISTORICAL_DEVELOPMENT` never satisfies Item 9 prospective gates.

## Next lawful operator action (Item 9, RTH only)

1. `python tools/imp.py item9 next-rth-preflight --json` (read-only).
2. During RTH with `READY_TO_COLLECT`: governed Mode B `--poll` from **ITEM9_FROZEN_COLLECTOR** worktree — not off-hours.
3. Post-receipt: `item9_corpus_status.py corpus-status` — no automatic calibration fitting.

## Doc map

| Topic | Engineering note |
| --- | --- |
| Program status | [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) |
| Next RTH runbook | [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md) |
| Item 9 operator | [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md) |
| Dual-corpus contract | [DUAL_CORPUS_EVIDENCE_CONTRACT.md](../architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md) |

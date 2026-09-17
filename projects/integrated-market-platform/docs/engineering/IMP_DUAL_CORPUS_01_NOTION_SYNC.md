# IMP-DUAL-CORPUS-01 — Notion sync summary (repo)

**Purpose:** Operator-facing snapshot for Notion or program dashboards. Repo authority remains [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).

| Field | Value |
| --- | --- |
| Current `origin/main` tip | `84d197d227b38665f4cdbfe6746fff48ef5542d6` (merge [#244](https://github.com/AdamEddahmouni/market-trading-platform/pull/244); lanes [#242](https://github.com/AdamEddahmouni/market-trading-platform/pull/242)–[#244](https://github.com/AdamEddahmouni/market-trading-platform/pull/244)) |
| Frozen Item 9 collector SHA | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` — Sep 17 Mode B epoch **closed** through 16:00 ET; do not retarget collector mid-epoch |
| Last verified | 2026-09-17 |

## Program truths (do not soften)

- **Item 9:** `PARTIAL` / **`NOT_CALIBRATED`**. Sample gate **`INSUFFICIENT_CALIBRATION_EVIDENCE`**. Floors: **20** included observations, **3** distinct US cash RTH dates, **5** evaluation rows (`MINIMUM_CLASS_COUNT`). This epoch (operator receipt dir): **1** corpus-admissible / **1** distinct RTH date — **below** all floors. Sep 17 `PATH_PROOF_ONLY` receipt is immutable.
- **Distinct prospective RTH dates (honest):** **1** / **3** required for Item 9 calibration sample gate (same epoch as above).
- **Historical development corpus:** Introduced on `main` via [#243](https://github.com/AdamEddahmouni/market-trading-platform/pull/243) — authority `HISTORICAL_DEVELOPMENT` only; `PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED`.
- **Historical data ≠ prospective gates:** Offline RTH bars and post-horizon labels do **not** satisfy Item 9 prospective calibration or FTEP empirical activation.
- **Post-horizon label architecture:** [#244](https://github.com/AdamEddahmouni/market-trading-platform/pull/244) — `POST_HORIZON_HISTORICAL_LABEL_EVIDENCE`; labels after horizon on historical windows; **do not** mutate prospective feature paths or Item 9 receipts.
- **Dual-corpus contract:** [#242](https://github.com/AdamEddahmouni/market-trading-platform/pull/242) — [DUAL_CORPUS_EVIDENCE_CONTRACT.md](../architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md); `UNTOUCHED_FORWARD_EVALUATION` protected from training/selection consumption.
- **Item 7:** **`ITEM7_PENDING_NATURAL_EVIDENCE`** / governed rows **0** — unchanged by dual-corpus landing; natural evidence only; **no** forced settlement.
- **PR #222:** Item 7 natural settlement — **still isolated** (not merged).
- **Phase 5.5B #196:** Superseded by [#224](https://github.com/AdamEddahmouni/market-trading-platform/pull/224); not an open queue member.
- **FTEP:** **not** `EMPIRICAL_ACTIVE`; empirical locks **0**.
- **Live execution:** **OFF** / forbidden.

## Doc map

| Lane | Engineering note |
| --- | --- |
| A | [IMP_DUAL_CORPUS_01_LANE_A_RECON.md](IMP_DUAL_CORPUS_01_LANE_A_RECON.md) |
| B | [IMP_DUAL_CORPUS_01_LANE_B_HISTORICAL_RTH.md](IMP_DUAL_CORPUS_01_LANE_B_HISTORICAL_RTH.md) |
| C | [IMP_DUAL_CORPUS_01_LANE_C.md](IMP_DUAL_CORPUS_01_LANE_C.md) |
| D (this increment) | Docs/status sync PR on `docs/dual-corpus-status-sync` |

# RTH 2026-09-15 live-integration test-gap audit

> **HISTORICAL_TRUTH** recovered in RTH15-00. Describes Sep 15 coverage gaps.
> Later `#203`–`#208` closed several software holes. Do not treat this matrix
> as the current test inventory (`tools/validation_manifest.json` is).

**Lane:** Isolated P9 (`diagnosis/test-gap-audit-20260915` from `origin/main`).
**Evidence class:** diagnosis of test coverage. Not a product-behavior change.
**Constraints honored:** existing gates not weakened; frozen RTH not edited;
no merge; no production files taken from P1–P4 / P2 / P3.

| Document | Purpose |
|----------|---------|
| [TEST_GAP_MATRIX.md](TEST_GAP_MATRIX.md) | Why pre-RTH validation passed while live composition failed; exact missing tests and owning lanes |
| [TEST_GAP_MATRIX.json](TEST_GAP_MATRIX.json) | Machine-readable copy of the same matrix |

This increment does **not** flip empirical gates, enable Live execution, or
claim FTEP `EMPIRICAL_ACTIVE`.

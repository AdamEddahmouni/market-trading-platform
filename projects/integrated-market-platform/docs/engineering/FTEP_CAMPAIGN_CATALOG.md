# FTEP forward-test campaign catalog

Status vocabulary (do not collapse these labels):

| Label | Meaning |
|-------|---------|
| `MANIFEST_FROZEN` | Campaign activation manifest is immutable; fingerprint is invariant. Distinct from preregistration. |
| `FROZEN_FOR_ACTIVATION` | Every required activation gate is satisfied **and** the manifest is frozen before the first qualifying prospective observation. Manifest freeze alone is not this state. |
| `SIGNAL_ONLY_AUTHORIZED` | Owner authorized SIGNAL_ONLY sessions via a committed receipt. Paper EXECUTION and Live remain unauthorized. Authorization is not activity. |
| `EMPIRICAL_ACTIVE` | At least one governed prospective session has started. Receipts and freeze do not imply this. |

Current program decision (2026-09-13, git tip `9cb541c`): **`FTEP_EMPIRICAL_NOT_READY`**. That is the activation-readiness label; it is **not** a catalog enum and does **not** start a session. Neither campaign below is `EMPIRICAL_ACTIVE`.

| Campaign | Slug | Status | Asset lane | Incremental cost | Notes |
|----------|------|--------|------------|------------------|-------|
| ES news catalyst (first) | `FTEP-V1-001` | **MANIFEST_FROZEN**; not `SIGNAL_ONLY_AUTHORIZED`; not `EMPIRICAL_ACTIVE` | `FUTURES_EQUITY_INDEX` / ES | $0 engineering; ES quote **not entitled** | Prospective disposition: `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`. Do not mutate manifest, OD fields, or universe. |
| US equity news catalyst (pivot) | `FTEP-V1-002` | **MANIFEST_FROZEN** + **SIGNAL_ONLY_AUTHORIZED**; empirical lock authorized via receipt; **not** `EMPIRICAL_ACTIVE` | `US_EQUITY` | $0 (owner Moomoo + Finviz Elite) | Frozen manifest + committed SIGNAL_ONLY receipt + empirical-lock receipt. Governed sessions **0**. **Not PROPOSED.** Paper EXECUTION / Live unauthorized. |

Stack evidence:

- V1-001: [`artifacts/ftep-v1-001/es-news-provider-stack-selection.json`](../../artifacts/ftep-v1-001/es-news-provider-stack-selection.json)
- V1-002: [`artifacts/ftep-v1-002/us-equity-provider-stack-selection.json`](../../artifacts/ftep-v1-002/us-equity-provider-stack-selection.json)
- V1-002 SIGNAL_ONLY receipt: [`artifacts/ftep-v1-002/signal-only-authorization-receipt-2026-09-12.json`](../../artifacts/ftep-v1-002/signal-only-authorization-receipt-2026-09-12.json)
- V1-002 empirical-lock receipt: [`artifacts/ftep-v1-002/empirical-lock-authorization-receipt-2026-09-12.json`](../../artifacts/ftep-v1-002/empirical-lock-authorization-receipt-2026-09-12.json)

Readiness:

```powershell
python3 tools/imp.py providers campaign-readiness FTEP-V1-001 --json
python3 tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

`FTEP-V1/0.1.0-PREREG` and frozen `PROTOCOL_REF.json` classification strings are **freeze-time / hash-bound**. Do not casual-edit them. Current campaign labels are this catalog + [GLOSSARY.md](../platform/GLOSSARY.md).

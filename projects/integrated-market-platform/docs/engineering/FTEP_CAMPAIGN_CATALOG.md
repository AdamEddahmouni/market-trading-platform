# FTEP forward-test campaign catalog

| Campaign | Slug | Status | Asset lane | Incremental cost | Notes |
|----------|------|--------|------------|------------------|-------|
| ES news catalyst (first) | `FTEP-V1-001` | **FROZEN** | `FUTURES_EQUITY_INDEX` / ES | $0 engineering; ES quote **not entitled** | Do not mutate manifest, OD fields, or universe. Prospective disposition: `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`. |
| US equity news catalyst (pivot) | `FTEP-V1-002` | **PROPOSED** (`PENDING_OWNER_DECISIONS`) | `US_EQUITY` | $0 (owner Moomoo + Finviz Elite) | Smallest $0 prospective path; freeze/empirical collection **not** authorized in this increment. |

Stack evidence:

- V1-001: [`artifacts/ftep-v1-001/es-news-provider-stack-selection.json`](../../artifacts/ftep-v1-001/es-news-provider-stack-selection.json)
- V1-002: [`artifacts/ftep-v1-002/us-equity-provider-stack-selection.json`](../../artifacts/ftep-v1-002/us-equity-provider-stack-selection.json)

Readiness:

```powershell
python tools/imp.py providers campaign-readiness FTEP-V1-001 --json
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

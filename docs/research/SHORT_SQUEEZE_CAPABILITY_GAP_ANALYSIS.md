# Short Squeeze Capability Gap Analysis (Deliverable 5)

| Capability | Finviz Elite | IBKR | SEC/EDGAR | FINRA | IMP fixtures | Gap |
|---|---|---|---|---|---|---|
| Real-time price | partial | yes | no | no | BIYA bars | — |
| Published SI | yes (lagged) | no | no | no | frozen rules | publication lag must gate |
| Float | yes | no | no | no | frozen | — |
| DTC (Finviz ratio) | yes | no | no | no | frozen | estimated DTC display-only |
| Borrow fee | no | partial/stub | no | no | none | **needs verified IBKR entitlement** |
| Borrow availability | no | partial | no | no | none | **gap** |
| Utilization | no | no | no | no | none | **major gap** |
| Shares on loan | no | no | no | no | none | **major gap** |
| Daily short volume | no | no | no | yes | none | flow only — not SI |
| FTD | no | no | no | partial | forbidden | intentionally excluded |
| Options chain/OI | no | partial | no | no | BIYA fixture | replay entitlement |
| Greeks/dealer γ | no | partial | no | no | fixture | **model not in squeeze core** |
| L2 / trades / CVD | no | partial | no | no | NVDA order flow | IMP whale lane only |
| News/catalyst | no | no | filings | no | catalyst fixture | NLP thesis invalidation **gap** |
| Social attention | no | no | no | no | none | **future** |

Fallback policy: **fail closed** — missing capability → `missing_capabilities[]`, never zero imputation.

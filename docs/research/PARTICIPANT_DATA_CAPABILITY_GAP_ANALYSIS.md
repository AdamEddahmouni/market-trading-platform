# Participant Intelligence — Data Capability Gap Analysis (Deliverable 7)

| Capability | Available (fixture) | Missing / delayed | Latency | PIT semantics | Identity resolution | Status |
|---|---|---|---|---|---|---|
| Form 4 insider transactions | BIYA fixture | Live EDGAR XML parser; ownership deltas; 10b5-1 flags | Days | Filing `available_time` | Named filer | PARTIAL |
| Form 3 initial ownership | Mapped in vocabulary | No dedicated parser | Days | Filing time | Named | RESEARCH |
| Form 5 annual | Not mapped | Full support | Days | Filing time | Named | MISSING |
| Schedule 13D | Event type only | Campaign objectives, stake table | Days | Filing time | Named fund/person | PARTIAL |
| Schedule 13G | Event type only | Passive vs activist distinction weak | Days | Filing time | Named | PARTIAL |
| Form 13F | Holdings + QoQ position change (fixture) | Shorts omitted, hedges omitted, live XML | ~45 days | **Filing only for copy** | Manager name | IMPLEMENTED |
| Block / large prints | NVDA fixture | Live tape; participant identity unknown | Real-time | Trade time | **Anonymous** | PARTIAL |
| Options large trades | BIYA fixture | Customer/dealer side; open/close | Near RT | Provider-dependent | **Unknown** | PARTIAL |
| COT positioning | ES fixture (F4) | Live COT; not in whale ledger | Weekly | Report `available_time` | Category only | AVAILABLE (Futures) |
| Order flow / CVD | NVDA fixture | Live MBO | Real-time | Trade time | **Forbidden to invent** | AVAILABLE (OF) |
| Metaorder inference | — | OF11 not started | — | Live-only constraints | Unknown institutional | MISSING |
| Short seller identity | — | Public disclosures sparse | Varies | Disclosure time | Sometimes named | MISSING |
| Crypto on-chain | Docs only | Wallet labels, cluster history | Minutes | `label_available_time` required | Probabilistic | NOT_AUTHORIZED |
| Prediction market participants | Docs only | Kalshi anonymous; Polymarket wallets | Varies | Resolution + label PIT | Wallet-level | NOT_AUTHORIZED |
| Copy-trading platform research | Enum only | LiteFinance etc. | Varies | Platform-dependent | Trader handles | RESEARCH_ONLY |
| Participant historical skill | — | Outcome-linked walk-forward store | — | Skill at t uses <t only | Per participant_id | MISSING |
| 10b5-1 plan indication | — | Structured extraction | — | Filing time | Named | MISSING |
| Institutional ownership (non-13F) | — | 13D/G partial | Days | Filing time | Named | PARTIAL |

## Licensing / cost notes

- Live EDGAR: public, rate-limited
- Unusual Whales / options flow: commercial, licensing required
- MBO / full depth: exchange fees
- Crypto labels: third-party, retrospective bias risk
- 13F: free but delayed; incomplete economic exposure

## Priority gaps for PI3

1. Live EDGAR with transaction-level Form 4 fields (quantity, price, ownership before/after)
2. 13D structured activist extraction
3. 13F quarter-over-quarter position change with strict `available_time`
4. Cross-lane publication of `InsiderEvidence` / `ActivistEvidence`
5. OF11 metaorder cooperation (no identity invention)

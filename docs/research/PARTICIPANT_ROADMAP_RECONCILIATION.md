# Six-Area Roadmap Reconciliation (Deliverable 2)

**Date:** 2026-08-19  
**Authority:** `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` + lane reconciliation docs

---

## Hierarchy

```text
PLATFORM (P0–P5)
│
├── DOMAIN INTELLIGENCE
│   ├── Short Squeeze (SS P0–P7)
│   ├── Options (O1–O11)
│   ├── Futures (F1–F11)
│   ├── Crypto (E0–E16) — NOT_AUTHORIZED
│   └── Prediction Markets (PM P0–P15) — NOT_AUTHORIZED
│
└── CROSS-DOMAIN INTELLIGENCE
    ├── Order Flow (OF1–OF12)
    ├── Market Context (MC1–MC16)
    └── Participant Intelligence (PI1–PI16)
```

Whale Revision 3 Phases 9–16 = **ingestion families** feeding Participant Intelligence.

---

## Shared prerequisites (parallelizable)

| Milestone | Blocks | Status |
|---|---|---|
| Platform P0 PIT/provenance | All lanes | MOSTLY DONE |
| Platform P2 physical P | Options, SS, Futures | DONE (fixture) |
| Platform P3 cross-lane evidence | All publishers | DONE |
| Platform P4 shared EV | Strategy selection | DONE (fixture) |
| Whale Phases 9–16 ledger | PI2+ disclosure bridge | DONE |

Participant PI1–PI2 can proceed **without blocking** SS/O/F/OF/MC active phases.

---

## Lane dependencies on Participant Intelligence

| Lane | Consumes from Participant | Does not delegate to Participant |
|---|---|---|
| Short Squeeze | Insider/activist/crowding/forced-flow evidence | Squeeze state machine |
| Options | Large customer persistence context | Signed flow, P vs Q, Greeks |
| Futures | Cross-asset crowding context | COT semantics, curve |
| Order Flow | — (Participant consumes OF) | CVD, OFI, metaorder primitives |
| Market Context | — (Participant consumes MC) | Event extraction, surprise |
| Shared EV | Copyability, mechanism, skill inputs | Opportunity fusion |

---

## Participant dependencies on other lanes

| PI Phase | Depends on | Reason |
|---|---|---|
| PI6 metaorder | OF4+, OF11 | Mechanical flow primitives |
| PI8 contextual intent | MC8+ | Pre/post catalyst timing |
| PI11 cross-asset | F4 COT | Category positioning |
| PI12 derivatives participant | O5 | Signed flow semantics |
| PI13 forced flow | OF + MC + F8 | Dislocation without catalyst |
| PI14 crypto | Crypto E-track | Wallet/entity PIT |
| PI15 prediction | PM P-track | Participant calibration |

---

## Conflicts resolved

| Conflict | Resolution |
|---|---|
| Whale 8 families vs PI architecture | PI consumes ledger; does not replace families |
| `futures_positioning` ledger vs COT F4 | PI11 consumes F4; ledger depth renamed `futures_depth` |
| Strategy WHALE_ALIGNED vs mechanism | PI9 gates alignment on mechanism + copyability |
| MC activist event vs PI activist | MC owns extraction; PI owns participant interpretation |
| OF metaorder vs PI metaorder | OF owns detection; PI owns lifecycle/copyability |

---

## Parallel work matrix (next 90 days)

| Track | Authorized work |
|---|---|
| SS | P2 live lending when vendor ready |
| Options | O10 research |
| Futures | F9 RV spreads |
| Order Flow | OF10 MBO |
| Market Context | MC2–MC4 |
| **Participant** | **PI5 walk-forward skill + cross-lane publish** |
| Platform | P0 bitemporal store, P1 catalyst runtime |

---

## Duplicate work forbidden

- Per-lane participant skill scores
- Per-lane copyability engines
- Options re-deriving insider semantics from raw calls
- SS inferring participant identity from CVD
- Universal whale score

See `PARTICIPANT_DISCREPANCY_REGISTER.md` for open items.

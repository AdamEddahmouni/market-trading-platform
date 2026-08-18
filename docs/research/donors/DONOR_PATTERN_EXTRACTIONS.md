# Donor pattern extractions (PORT_ADAPT)

Independent reimplementations of donor subproject patterns inside
`integrated-market-platform`. Donor source trees are **not** copied.

| Donor | Pattern | IMP module | Status |
|---|---|---|---|
| tradingCVDBubble | Lee-Ready aggressor, BVC, OFI | `donor_patterns/cvd_formulas.py` | Implemented (stdlib) |
| short-squeeze-project | Freshness/missingness/provenance gates | `donor_patterns/provenance_gates.py` | Implemented |
| short-squeeze-project | Frozen readiness summaries | `donor_patterns/provenance_gates.py` | Implemented |
| Professor brief + squeeze SEC | EDGAR whale event vocabulary | `donor_patterns/edgar_whale.py` | Implemented |
| Phase 9 whale ledger | Fixture-first SEC EDGAR ingestion + ledger | `providers/` | **Complete** — offline BIYA fixture |
| Phase 10 order_flow | Fixture-first NVDA CVD slice + ledger | `providers/adapters/fixture_order_flow.py` | **Complete** — ADMITTED-CVD-NVDA-ORDERFLOW-001 |
| Phase 11 options | Fixture-first BIYA options slice + ledger | `providers/adapters/fixture_options.py` | **Complete** — ADMITTED-OPTIONS-BIYA-001 |
| Phase 12 large_transactions | Fixture-first NVDA large-print slice + ledger | `providers/adapters/fixture_large_transactions.py` | **Complete** — ADMITTED-LARGE-PRINTS-NVDA-001 |
| Phase 13 order_book | Fixture-first NVDA depth slice + ledger | `providers/adapters/fixture_order_book.py` | **Complete** — ADMITTED-L2-NVDA-001 |
| Eric_futuresX | ES contract roll, RTH gate, depth imbalance signal | `donor_patterns/futures_lane.py` | Implemented |
| Phase 14 futures | Fixture-first ES depth slice + ledger | `providers/adapters/fixture_futures.py` | **Complete** — ADMITTED-L2-ES-001 |
| Eric_futuresX | Read-only HTTP bridge | `Eric_futuresX-main/.../scripts/bridge_server.py` + `donor_bridge/futures_client.py` | **Complete** — optional `:8788` |
| internship-project | Catalyst confidence/lean gates | `donor_patterns/catalyst_lane.py` | Implemented |
| internship-project | Options liquidity/score lane | `donor_patterns/options_lane.py` | Implemented |
| internship-project | Read-only demo state bridge | `donor_bridge/internship_client.py` + `/explore/catalyst`, `/workspace/{symbol}/catalyst` | **Complete** — read-only lane closed |
| short-squeeze-project | Read-only explore API bridge | `donor_bridge/` + UI `/explore`, `/workspace/{symbol}/squeeze` | **Complete** — read-only lane closed |
| short-squeeze-project | Historical calibration cohort projection | `donor_bridge/historical_cohort.py` + `data/historical_squeeze_cohort_v1.json` | **Complete** — n=30 fixture; workspace + RESEARCH panels |

## Governance notes

- Whale ingestion for non-disclosure families, broker adapters, and live/paper execution remain unauthorized per Phase 8 limitations.
- `donor_patterns/*` modules are research/reference implementations; Phase 9 wires fixture-first EDGAR disclosure only.
- UI explore bridge fetches `http://127.0.0.1:8787` only when short-squeeze FROZEN_DEMO is running locally.
- Workspace squeeze panel uses `GET /workspace/{symbol}/squeeze` (see [SHORT_SQUEEZE_LANE.md](../../integration/SHORT_SQUEEZE_LANE.md)).
- Futures workspace uses `GET /workspace/ES/futures` (see [FUTURES_LANE.md](../../integration/FUTURES_LANE.md)).

## Verification

```bash
cd integrated-market-platform
python -m unittest tests.donor_patterns.test_donor_patterns
python -m unittest tests.donor_bridge.test_explore_bridge
python -m unittest tests.donor_bridge.test_workspace_squeeze
python -m unittest tests.donor_bridge.test_catalyst_bridge
python -m unittest tests.integration.test_squeeze_lane_acceptance
```

## Next governed steps (not implemented here)

1. Admit NVDA CVD demo fixture or Moomoo paper L2 adapter under new ADR.
2. Tradier sandbox live adapter behind provider contracts.
3. Project options/CVD lanes into specialized workspaces when capabilities exist.

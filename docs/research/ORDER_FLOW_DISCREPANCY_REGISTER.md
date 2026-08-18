# Order Flow Discrepancy Register (Deliverable 4)

| ID | Existing behavior | Why incomplete/incorrect | Evidence | Risk | Recommended change | Affected files | Owner | Phase | Priority |
|---|---|---|---|---|---|---|---|---|---|
| OF-D01 | Fixture ingest reads pre-baked `delta` | Runtime classification not applied | `fixture_order_flow.py` L97–100 | Misleading quality labels | Wire `classify_aggressor` when tick data available; bar path uses `classify_bar_delta` | `fixture_order_flow.py` | Order Flow | OF1 | P0 |
| OF-D02 | No `ClassifiedTrade` at ingest | Missing canonical trade record | Audit | Blocks MBO, execution sim | `order_flow/contracts.py` + ingest pipeline | `order_flow/` | Order Flow | OF1 | P0 |
| OF-D03 | NVDA momentum vs ES contrarian imbalance | Same ratio, opposite labels | `order_book_lane` vs `futures_lane` | Cross-lane confusion | Order Flow owns raw `BookPressureEvidence`; domains apply interpretation policy | Both lanes | Order Flow + Futures | OF3 | P1 |
| OF-D04 | `futures_positioning` for depth data | Misleading whale family name | `FUTURES_CURRENT_STATE_AUDIT.md` | Semantic pollution | Rename to `futures_depth` in future ADR | Phase 14 envelopes | Platform | F1 | P1 |
| OF-D05 | OFI uses BBO only | Multi-level fixture ignored for OFI | `snapshot_ofi` | Understates book flow | OF4 multi-level OFI with `ofi_method` versioning | `order_book_lane.py` | Order Flow | OF4 | P1 |
| OF-D06 | No CVD confidence in workspace | Unknown/inferred not surfaced | Pre-OF2 | Overconfident CVD display | `cvd_summary` in payload | `projections.py` | Order Flow | OF2 | P0 |
| OF-D07 | `BOOK_IMBALANCE_*` never emitted | Contract defined, unused | `cross_lane/evidence.py` | Missing cross-lane value | `build_cross_lane_snapshot_from_order_book` | `cross_lane_adapter.py` | Order Flow | OF3 | P1 |
| OF-D08 | `AGGRESSIVE_SELL_PRESSURE` never emitted | Buy-only detection | `cross_lane_adapter.py` | Asymmetric evidence | Emit sell pressure symmetrically | `cross_lane_adapter.py` | Order Flow | OF2 | P1 |
| OF-D09 | Bar simulator only | No book-aware execution | `execution/simulator.py` | Invalid microstructure backtests | Tiered book sim (OF9) | `execution/` | Platform | OF9 | P2 |
| OF-D10 | Live futures bridge OFI=0 | No prev snapshot | `futures_projections.py` | Lost OFI on bridge | Carry prev snapshot or degrade confidence | `futures_projections.py` | Futures | F3 | P2 |
| OF-D11 | No sequence-gap book invalidation | Corrupt book could emit OFI | Roadmap | Bad research | `book_state_valid=false` on gap | `order_flow/` (future) | Order Flow | OF4 | P1 |
| OF-D12 | No liquidity engine | Withdrawal/replenishment missing | Roadmap | CVD-only blind spots | `order_flow/liquidity.py` | `order_flow/` | Order Flow | OF6 | P2 |

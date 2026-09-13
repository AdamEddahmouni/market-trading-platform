# Paper execution calibration roadmap

**Lane:** H | **Date:** 2026-09-12  
**Contract:** `PAPER_SIMULATOR_CALIBRATION_CONTRACT.md`

## Three-layer model (summary)

1. **Structural** — Paper lifecycle, G13 canonical portfolio (complete with exceptions).
2. **Behavioral** — Slippage/spread/latency models (partial; numerics often UNSET).
3. **Empirical** — Forward-test calibration vs live observational fills (blocked).

## Current blockers

- Calibration metric gates **UNSET/BLOCKING** per contract.
- FTEP campaign not authorized — no empirical lock files.
- Foreground Wave B hooks exist on `work/ftep-v1-activation` (not on overnight base SHA).

## Roadmap

| Step | Owner | Dependency |
|---|---|---|
| Set baseline numerics in manifest | Owner | OWNER-OD decisions |
| Run fixture calibration comparator | Engineering | Wave B tooling (foreground) |
| Record divergence taxonomy outcomes | QA | Paper forward sessions |
| Promote to VERIFIED capability row | Governance | MARKET_DATA_CAPABILITY_CONTRACT |

## Overnight

**RESEARCH_COMPLETE** — no changes to `paper_projections.py` (no-touch).

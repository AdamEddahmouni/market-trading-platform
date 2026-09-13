# IMP Project Status

**Status:** 2026-09-11 snapshot.  
**Last updated:** 2026-09-11 (pre-implementation planning closure)  
**Canonical remote baseline reviewed:** `main@a4858103baa3531051791a632ed36a9339fd6414` (PR #18 merged)

> **Snapshot banner:** This document is a 2026-09-11 snapshot at `main@a4858103`. It is **not** current campaign state. Current program truth: [PROGRAM_STATUS.md](platform/PROGRAM_STATUS.md). Current FTEP campaigns: [FTEP_CAMPAIGN_CATALOG.md](engineering/FTEP_CAMPAIGN_CATALOG.md).

For the deep whole-program state matrix, see [Program Status](platform/PROGRAM_STATUS.md). For the current FTEP/Paper doctrine, see [IMP Scope, FTEP, and Paper-Validation Doctrine](architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md).

## What IMP is

IMP is a **multi-strategy, multi-asset opportunity-discovery and governed decision/Paper-execution platform**. The professor-directed news/catalyst program controls near-term sequencing but does not redefine the product. FTEP is the reusable Forward-Test Experimental Protocol; ES/news is only the candidate first bounded campaign.

Operating modes remain:

- **Demo** — fixture/replay exploration.
- **Paper** — simulated execution under explicit authority gates.
- **Live** — observational/read-only capabilities where verified; production broker execution remains separately unauthorized.

## Current canonical checkpoint

| Area | Current state |
|---|---|
| G0–G15 engineering foundation | Accepted with documented limitations |
| Governed Paper forward-testing bridge | `COMPLETE` / canonical |
| PD-09 durable forward-test persistence | `COMPLETE` / merged in PR #18; restart-safe SQLite path exists when persistent state is enabled |
| FTEP-V1 preregistration | `PLANNED / PRE-REGISTERED / NOT YET EMPIRICAL EVIDENCE` |
| FTEP campaign activation | **NOT YET FROZEN/ACTIVE** — unresolved activation gates remain |
| Strategy research program | Broad planning complete across major lanes; empirical validation remains lane-specific and incomplete |
| Internal Paper simulator realism | **NOT PRESUMED MARKET GROUND TRUTH** — calibration required for execution-bearing claims |
| Live production execution | **NOT AUTHORIZED** |

## Paper evidence doctrine

Prospective Paper evidence separates three layers:

1. **Market Evidence** — lawful real prospective market/news/reference observations where possible.
2. **IMP Execution Simulation** — IMP's hypothetical orders/fills/positions/P&L.
3. **External Simulation Comparator** — suitable independent Paper/sandbox/replay environment used as a challenger, never as ground truth.

See [Paper Simulator Calibration & Validation Contract](architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md) and [Market Data Capability Contract](architecture/MARKET_DATA_CAPABILITY_CONTRACT.md).

## FTEP architecture

The reusable protocol is now explicitly layered:

`FTEP Core -> Asset-Class Profile -> Strategy Profile -> Campaign Manifest`

Current pre-implementation documents:

- [FTEP Core V1](engineering/ftep/FTEP_CORE_V1.md)
- [Futures Asset-Class Profile V1](engineering/ftep/assets/FUTURES_PROFILE_V1.md)
- [News / Catalyst Strategy Profile V1](engineering/ftep/strategies/NEWS_CATALYST_PROFILE_V1.md)
- [Campaign Manifest Template V1](engineering/ftep/CAMPAIGN_MANIFEST_TEMPLATE_V1.md)
- [FTEP Activation & Pre-Implementation Gates](engineering/FTEP_ACTIVATION_GATES.md)
- Existing preregistration: [Forward-Test Experimental Protocol V1](engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md)

The existing `FTEP-V1/0.1.0-PREREG` document is a preregistration/design freeze with `OPEN DECISION` items. It is **not** the final campaign-activation freeze.

## Strategy and Opportunity Engine governance

A strategy does not have one authoritative maturity flag. Canonical readiness is a vector covering research, data/rights, implementation, OOS, shadow, Paper, execution calibration, Opportunity Engine integration, portfolio/risk integration and separately governed Live eligibility. See [Strategy Readiness Model](research/STRATEGY_READINESS_MODEL.md).

All future strategy families should converge on the common [IMP Opportunity Contract](architecture/OPPORTUNITY_CONTRACT.md) while preserving strategy-specific mechanisms, uncertainty, horizons and execution requirements. One Opportunity Engine does not require one universal scalar score.

## Current pre-implementation blockers before the first qualifying ES/news campaign

The first empirical campaign must not be activated until the required gates in [FTEP Activation & Pre-Implementation Gates](engineering/FTEP_ACTIVATION_GATES.md) are resolved. Material open items include:

- fresh private/local provider configuration audit, including whether Alpaca or any other previously configured environment is actually present now;
- lawful prospective ES market-data selection plus capability/entitlement/use-right verification;
- final Futures and News/Catalyst profile bindings for the campaign;
- exact dated ES contract and session window;
- external futures-capable comparator audit if execution realism is in scope;
- simulator calibration plan and **pre-registered numeric divergence tolerances**;
- exact Paper account/mode, signal-only vs execution mode, sizing/order/cost rules;
- horizons, cohort sufficiency, analysis and multiple-testing rules;
- immutable activation manifest with repository SHA and artifact paths.

These are deliberate activation prerequisites, not evidence that the planning architecture is incomplete.

## Next work sequence

1. Reconcile Notion and repository authorities to `main@a4858103` and this doctrine.
2. Audit private/local provider state without exposing secrets.
3. Verify campaign-suitable ES market evidence and rights.
4. Audit a futures-capable external simulation comparator for the exact campaign needs.
5. Establish/calibrate simulator behavior and freeze justified numeric tolerances.
6. Resolve every activation decision into an immutable campaign manifest.
7. Only then mark the first campaign `FROZEN_FOR_ACTIVATION` and begin qualifying prospective evidence.
8. Reuse the same FTEP Core and evidence doctrine across other strategy/asset families.

## Boundaries

- No campaign is active merely because a preregistration document exists.
- No software test, replay or Paper fill proves market edge by itself.
- No external Paper/sandbox environment is market ground truth.
- No paid service, trial or entitlement is activated without explicit owner authorization.
- No FTEP/Paper outcome grants Live execution authority.

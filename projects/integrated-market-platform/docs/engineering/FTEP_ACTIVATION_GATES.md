# FTEP Activation & Pre-Implementation Gates

**Classification:** `CURRENT_CANONICAL_GOVERNANCE`  
**Established:** 2026-09-11  
**Applies to:** activation of the first and subsequent empirical forward-test campaigns

This document separates **protocol preregistration** from **campaign activation**. The existing `FTEP-V1/0.1.0-PREREG` document is a design/preregistration artifact with unresolved decisions. It is not an activated campaign and it is not empirical evidence.

Provider selection is governed by [IMP Provider Universe, Audit & Integration Strategy](../providers/PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md): **catalog broadly, audit current access first, derive coverage gaps, integrate selectively, and bind exact providers only when campaign requirements are known.**

## Current provider-access facts

User-confirmed current resources include **Finviz access** and **Moomoo OpenD available/running on the free plan**. These facts establish audit priority, not campaign suitability. Exact tiers, entitlements, data modes, asset/depth coverage, permitted use and comparator capability remain activation evidence that must be measured rather than inferred.

## Gate summary

A campaign may be labeled `FROZEN_FOR_ACTIVATION` only when every required gate below is satisfied and the resulting activation manifest is immutable/versioned before the first qualifying prospective observation.

| Gate | Requirement | Current status at runtime baseline `main@a4858103` |
|---|---|---|
| G-A0 | Durable forward-test persistence and restart/idempotency | `PASS` — PD-09 merged |
| G-A1 | FTEP Core version bound | `PLANNED` — doctrine established; campaign binding pending |
| G-A2 | Asset-Class Profile bound | `BLOCKING` for first ES campaign until Futures Profile is frozen |
| G-A3 | Strategy Profile bound | `BLOCKING` until News/Catalyst profile is frozen for campaign use |
| G-A4 | Campaign identity and source SHA bound | `BLOCKING` until activation manifest is created |
| G-A5 | Current-access/private provider audit | `BLOCKING` — audit Finviz, Moomoo OpenD, IBKR, Tradier, Alpaca/local state and relevant existing APIs without exposing secrets |
| G-A5A | Provider Capability Matrix complete for first-campaign candidates | `BLOCKING` |
| G-A5B | Strategy/evidence Coverage-Gap Map complete | `BLOCKING` — new integration work must be justified by named gaps or deliberate challenger roles |
| G-A6 | Market Data Capability Contract satisfied | `BLOCKING` for ES prospective evidence |
| G-A7 | Entitlement/use-right verification satisfied | `BLOCKING` for each campaign-bound external source |
| G-A8 | External comparator capability audit | `BLOCKING` if execution realism is part of the first campaign claim |
| G-A9 | Simulator Calibration Contract + numeric thresholds frozen | `BLOCKING` for execution-bearing evidence |
| G-A10 | Account/mode binding | `BLOCKING` until exact Paper account/mode chosen; Live prohibited |
| G-A11 | Instrument and contract-month binding | `BLOCKING` for futures; continuous futures cannot be executable |
| G-A12 | Session/calendar/time-zone rules bound | `BLOCKING` |
| G-A13 | Candidate generation/cadence/overlap rules bound | `BLOCKING` |
| G-A14 | Signal-only vs execution mode bound | `BLOCKING` |
| G-A15 | Sizing, order-policy, cost/slippage assumptions bound | `BLOCKING` for execution mode |
| G-A16 | Primary/secondary horizons and metrics bound | `BLOCKING` |
| G-A17 | Rejection/exclusion/invalidation criteria bound | `PARTIAL` — prereg contains defaults; activation-specific finalization required |
| G-A18 | Minimum campaign duration/cohort sufficiency bound | `BLOCKING` |
| G-A19 | Analysis/multiple-testing/segmentation plan bound | `BLOCKING` |
| G-A20 | Shakedown segment policy | `BLOCKING` — empirical shakedown must be separated from qualifying cohort |
| G-A21 | Artifact paths, manifest hashing and reproducibility package | `BLOCKING` |
| G-A22 | Owner/authority approval of unresolved campaign choices | `BLOCKING` |

`BLOCKING` means the first empirical campaign must not be treated as activated until the gate is resolved. It does **not** mean runtime implementation is missing unless specifically stated.

## Required activation manifest

The final activation manifest must contain at minimum:

- `campaign_id`;
- FTEP Core version;
- Asset-Class Profile version;
- Strategy Profile version;
- repository source SHA;
- machine-readable manifest version/hash;
- Paper account identity and execution mode;
- exact instrument(s), futures exchange/contract month where relevant;
- market/news/provider source bindings and capability-contract IDs;
- entitlement/use-right verification date/status;
- comparator provider/environment and known limitations, if used;
- simulator calibration-contract version;
- frozen numeric acceptance/divergence thresholds;
- session/calendar/time-zone rules;
- candidate generation, dedupe and overlap rules;
- strategy/baseline/treatment versions;
- AI model/prompt/source policy versions if an AI arm is active;
- order types, sizing, costs/slippage/fees/margin assumptions;
- decision and evaluation horizons;
- required metrics and disposition rules;
- exclusion/rejection/invalidation rules;
- minimum qualifying sessions/days/decisions and regime-coverage expectations;
- shakedown/qualifying-cohort boundary;
- analysis, segmentation and multiple-testing policy;
- artifact/evidence storage locations;
- explicit statement that Live authority is not granted.

## First-campaign sequencing

The current first-campaign candidate remains the professor-priority news/catalyst lane on ES, but it is not binding until the activation manifest is frozen.

Recommended sequence:

1. Maintain the broad provider universe/catalog; catalog inclusion is research, not implementation.
2. Audit **current access first** in this order unless a named blocker demands otherwise: Finviz -> Moomoo OpenD -> IBKR -> Tradier -> Alpaca/local/private state -> relevant existing news/data APIs.
3. Complete the Provider Capability Matrix for those resources and any immediate campaign candidates.
4. Derive the strategy/evidence Coverage-Gap Map and identify the smallest sufficient ES/news stack.
5. Select and verify lawful prospective ES market evidence with sufficient timing/coverage for the intended claims.
6. Freeze the Futures Asset-Class Profile.
7. Freeze the News/Catalyst Strategy Profile.
8. Audit one or more futures-capable external simulation comparators for the exact campaign needs.
9. Implement only missing canonical provider adapters, normalization or comparison tooling required by the selected stack.
10. Establish the Simulator Calibration & Validation Contract and justified numeric thresholds.
11. Run a non-qualifying calibration/shakedown segment if required; retain all discrepancies.
12. Resolve every remaining `OPEN DECISION` from `FTEP-V1/0.1.0-PREREG` in the activation manifest.
13. Bind exact repository SHA, providers, Paper account, contract month, rules and metrics.
14. Mark the manifest `FROZEN_FOR_ACTIVATION` before any qualifying prospective observation.
15. Run the qualifying campaign without changing frozen rules.
16. Close with `KEEP`, `REJECT`, `REPEAT`, `MODIFY`, or `BLOCKED` against preregistered criteria.

## Provider-selection constraints

- Current access is evaluated before new procurement.
- Finviz should initially be treated as a discovery/screening/context resource unless audit proves a stronger role.
- Moomoo OpenD should initially be treated as an available observational/data resource and possible comparator only to the extent its exact free-plan entitlements and simulation capabilities are verified.
- A provider may be integrated without becoming campaign-authoritative.
- A provider may be authoritative for one evidence type and context/challenger-only for another.
- No new integration is required merely because a provider exists. It must close a named coverage gap, supply a deliberate challenger/redundancy function, or remove a measured bottleneck.
- No paid subscription, trial, market-data entitlement or account binding is authorized by this document.

## Change control after activation

Any material change to source/provider binding, data mode, asset/instrument, strategy logic, prompt/model, candidate generation, horizon, sizing, order policy, transaction-cost treatment, acceptance threshold, exclusion rule or analysis plan requires either:

- a new campaign/version; or
- explicit invalidation of the current campaign with the reason preserved.

Operational bug fixes that do not change empirical semantics must still be recorded and source-SHA rebound before qualifying evidence resumes.

## What is not required before all implementation

These gates govern the first empirical campaign. They do not prohibit implementation of clearly prerequisite infrastructure such as provider capability auditing, market-data adapters, calibration harnesses, immutable manifests, asset/strategy profiles or Opportunity Contract plumbing. Those implementations must themselves preserve the doctrine in `IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md` and the provider strategy in `PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md`.

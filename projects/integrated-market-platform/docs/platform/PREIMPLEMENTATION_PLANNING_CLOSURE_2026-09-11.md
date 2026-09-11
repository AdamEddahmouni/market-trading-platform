# IMP Pre-Implementation Planning Closure — 2026-09-11

**Classification:** `CURRENT_CANONICAL_PLANNING_CLOSURE`  
**Reviewed baseline:** `main@a4858103baa3531051791a632ed36a9339fd6414`  
**Runtime code changed by this closure:** **No**

## Closure result

**PLANNING ARCHITECTURE COMPLETE FOR THE CURRENT STATE, WITH EXPLICIT EXTERNAL/CAMPAIGN ACTIVATION GATES.**

The project no longer treats ES/news, FTEP, the internal simulator, or any external Paper broker as synonymous with IMP or with market truth. The reusable pre-implementation contracts now define how strategies, assets, data, simulation, comparison and evidence must fit together before qualifying prospective campaigns begin.

This closure does **not** claim that provider credentials, market-data entitlements, external Paper environments or empirical calibration have been completed. Those depend on private/local/external state and remain explicit activation gates rather than hidden assumptions.

## Canonical architecture established

- [IMP Scope, FTEP, and Paper-Validation Doctrine](../architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md)
- [Market Data Capability Contract](../architecture/MARKET_DATA_CAPABILITY_CONTRACT.md)
- [Paper Simulator Calibration & Validation Contract](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md)
- [IMP Opportunity Contract](../architecture/OPPORTUNITY_CONTRACT.md)
- [Strategy Readiness Model](../research/STRATEGY_READINESS_MODEL.md)
- [FTEP Core V1](../engineering/ftep/FTEP_CORE_V1.md)
- [Futures Asset-Class Profile V1](../engineering/ftep/assets/FUTURES_PROFILE_V1.md)
- [News / Catalyst Strategy Profile V1](../engineering/ftep/strategies/NEWS_CATALYST_PROFILE_V1.md)
- [Campaign Manifest Template V1](../engineering/ftep/CAMPAIGN_MANIFEST_TEMPLATE_V1.md)
- [FTEP Activation & Pre-Implementation Gates](../engineering/FTEP_ACTIVATION_GATES.md)

## Current implementation truth reconciled

PR #18 / `main@a4858103` already contains PD-09 durable forward-test persistence. Therefore the old status statement “durable persistence is the next increment” is obsolete.

The existing [Forward-Test Experimental Protocol V1](../engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) remains useful as a preregistration artifact, but its `OPEN DECISION` sections mean it is not yet a frozen campaign activation manifest.

## Evidence architecture

Paper evidence now has three explicit truth layers:

1. real prospective Market Evidence;
2. IMP's simulated execution/accounting behavior;
3. independent external simulation comparators.

External Paper/sandbox behavior is retained as a challenge/benchmark, never promoted to ground truth. Execution-bearing claims require a scoped calibration contract and pre-registered numeric tolerance gates.

## FTEP architecture

FTEP is reusable and layered:

`FTEP Core -> Asset-Class Profile -> Strategy Profile -> Campaign Manifest`

This prevents the first campaign from becoming the permanent protocol and prevents asset-specific execution semantics from leaking into universal rules.

## Strategy architecture

Strategy readiness is multidimensional. Research maturity, data rights, implementation, OOS evidence, shadow evidence, Paper evidence, execution calibration, Opportunity Engine integration, portfolio/risk integration and Live eligibility remain independently visible.

A common Opportunity Contract supplies comparability and explainability without requiring one universal magic score.

## First-campaign state

The professor-priority ES/news campaign remains a **candidate first campaign**, not an active one. Before qualifying prospective evidence, the activation manifest must resolve the explicit gates for:

- current private/local provider configuration;
- lawful prospective ES data and rights;
- exact contract month/session/data bindings;
- comparator suitability;
- simulator calibration and quantitative thresholds;
- Paper account/mode and execution policy;
- horizons/cohort/metrics/multiple-testing rules;
- immutable manifest/SHA/artifact bindings.

## Safe handoff to implementation

Implementation may now proceed only against these contracts, beginning with prerequisites required to satisfy an activation gate. Runtime work must not silently redefine the doctrine.

Examples of valid next implementation increments include provider capability-audit tooling, market-data adapters required by a selected lawful ES source, calibration/reconciliation harnesses, machine-readable campaign manifests, Opportunity Contract plumbing, and readiness-vector representation.

Starting a qualifying campaign, enabling Live trading, binding an unverified private account, or activating a paid source is **not** authorized by this closure.

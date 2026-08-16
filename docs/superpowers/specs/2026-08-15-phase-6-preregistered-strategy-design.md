# Phase 6 — preregistered strategy (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-16  
**Scope:** Phase 6 only — strategy specification, preregistration identity, interpretation, abstention, walk-forward integration  
**Prerequisites:** Phase 0 `PASS` through Phase 5R `PASS`

## 1. Purpose

Prove preregistered strategy semantics on the admitted equity intraday fixture: immutable
strategy specification identity, mandatory preregistration before interpretation, explicit
signal or abstention with reason codes, and deterministic strategy evaluation integrated
with Phase 5R walk-forward forecasts — without risk sizing, execution simulation,
provider, or broker work.

## 2. In scope

- `StrategySpec` with alignment type, hypothesis, and evidence requirements.
- Preregistration record bound to strategy identity hash before any interpretation.
- `StrategyInterpretation` mapping forecast + bar-derived features → signal or abstention.
- Fail-closed abstention when institutional evidence is `unavailable` for whale-aligned specs.
- Walk-forward integration reusing Phase 5R dataset, targets, and naive baseline forecasts.
- Adversarial fixtures for missing preregistration, silent abstention bypass, and whale override.
- Assertion registry for `STRAT-001`, `ABST-001`, `PIT-STRAT-001`, `DET-001`, and `SAFE-003`.

## 3. Out of scope

- Risk sizing, portfolio simulation, cash/position/P&L reconciliation (Phase 7).
- Order intent, execution, broker, or provider integration.
- Neural networks or third-party ML runtimes.
- Whale ingestion or institutional evidence beyond Phase 5 fail-closed interfaces.
- Research UI, production frontend, or live/paper orders.
- ES futures or unsupported capability upgrades.

## 4. Completion definition

Phase 6 is complete when preregistered strategy interpretation passes on the admitted
fixture, all five assertions pass, strategy evaluation determinism is proven under
network denial, and `phase6.pass_publication` is published without beginning Phase 7.

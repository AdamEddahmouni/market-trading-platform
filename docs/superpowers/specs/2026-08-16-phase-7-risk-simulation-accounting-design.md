# Phase 7 — risk, simulation, and accounting (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-16  
**Scope:** Phase 7 only — independent risk, conservative bar-level simulation, cash/position/P&L reconciliation, and attribution  
**Prerequisites:** Phase 0 `PASS` through Phase 6 `PASS`

## 1. Purpose

Prove independent risk decisions, conservative bar-level execution simulation, exact
fill-driven accounting, and structured attribution on the admitted equity intraday
fixture — without broker routing, provider integration, or live/paper orders.

## 2. In scope

- `RiskPolicy` with preregistered limits and kill-switch state.
- `OrderIntent` derived from Phase 6 strategy signals (separate contract).
- Independent `RiskDecision` returning `APPROVE`, `REJECT`, or `RESIZE`.
- Bar-only conservative simulator aligned to `BAR_OHLCV_1M` capability manifest.
- Exact integer ledger for orders, fills, positions, cash, fees, and realized P&L.
- Independent reconciliation reproducing authoritative ledgers exactly.
- Attribution records for risk, simulation, and cost outcomes.
- Adversarial fixtures for kill-switch rejection and pre-activation fill attempts.
- Assertion registry for `EXE-001`, `EXE-002`, `EXE-003`, and `SAFE-003`.

## 3. Out of scope

- Broker routing, live/paper orders, or provider integration.
- MBO/MBP queue models, sweep claims, or intrabar path simulation.
- ES futures, neural networks, or third-party ML runtimes.
- Research UI, production frontend, or Phase 8 end-to-end acceptance.
- Strategy reinterpretation or preregistration changes.

## 4. Completion definition

Phase 7 is complete when risk, simulation, and accounting pass on the admitted
fixture, all four assertions pass, simulation determinism is proven under network
denial, and `phase7.pass_publication` is published without beginning Phase 8.

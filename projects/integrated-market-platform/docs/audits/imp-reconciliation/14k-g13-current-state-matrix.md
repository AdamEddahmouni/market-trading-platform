# 14k — G13 Current-State Matrix (Canonical Multi-Asset Paper Execution)

**Status:** CLOSED (2026-09-09 closure validation) — G13 canonical derivative Paper execution + margin facts  
**Starting FULL baseline:** 4355 / 48 / 0 / 0  
**Closure FULL:** 4380 / 48 / 0 / 0 (+25)  
**G13 scope:** Options/futures Paper submit/fill → CanonicalPortfolio; margin facts; fail-closed risk

## Roadmap reconciliation

G12 backlog explicitly deferred Paper options/futures E2E and futures margin before Wave 7 frontend. G13 is the correct next increment — **Wave 7 NOT_READY** until Paper derivative lifecycle is operationally proven.

## Paper execution forensics (post-G13)

| Asset | Preview | Risk | Submit | Working | Fill | Replace | Cancel | Portfolio | Cash | Margin | Authority |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EQUITY | CANONICAL | CANONICAL | CANONICAL | CANONICAL | CANONICAL | CANONICAL | CANONICAL | LEGACY+COMPAT | CANONICAL | N/A | LEGACY_LEDGER (equity parity) |
| OPTION_CONTRACT | CANONICAL | CANONICAL | CANONICAL | CANONICAL | CANONICAL | **CANONICAL** | **CANONICAL** | **CANONICAL** | **CANONICAL** | FAIL_CLOSED short open | **CanonicalPortfolio** |
| FUTURE_CONTRACT | CANONICAL | CANONICAL+margin | CANONICAL | CANONICAL | CANONICAL | **CANONICAL** | **CANONICAL** | **CANONICAL** | **CANONICAL** (no notional debit) | **EXPLICIT_FACTS** | **CanonicalPortfolio** |
| CRYPTO_PAIR | CANONICAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | N/A | SECONDARY |

## Authority map (after G13)

| Component | Role |
|---|---|
| `portfolio/canonical.py` (CanonicalPortfolio) | **AUTHORITATIVE** for option/future Paper positions + cash |
| `portfolio/paper_fill.py` | **AUTHORITATIVE** fill → portfolio mutation |
| `risk/margin_facts.py` | **AUTHORITATIVE** margin fact admission (no invented formulas) |
| `portfolio/ledger.py` | **AUTHORITATIVE** equity Paper parity (unchanged) |
| `portfolio/options_ledger.py` | **NON_AUTHORITATIVE** compatibility (O9 lane) |
| `paper/ledger.py` | **AUTHORITATIVE** event sourcing; derivative fills route to canonical |

## Margin authority

| Item | Status |
|---|---|
| MARGIN_INFRASTRUCTURE_COMPLETE | **YES** — `MarginRequirementFacts`, admission, pretrade integration |
| BROKER_MARGIN_MODEL_AVAILABLE | **NO / LIMITED** — no universal IBKR/CME production margin model; explicit facts or `FixtureFuturesMarginProvider` (FIXTURE / TEST / AUTHORIZED_STATIC_ADAPTER) only |

## Backlog closure (G13)

| Item | Status |
|---|---|
| OPTIONS_PAPER_E2E | **COMPLETE** (buy-to-open, multiplier cash, canonical portfolio) |
| FUTURES_PAPER_E2E | **COMPLETE_WITH_EXPLICIT_MARGIN_FACT_REQUIREMENT** |
| FUTURES_MARGIN_INFRASTRUCTURE | **COMPLETE** |
| LEGACY_OPTIONS_LEDGER | **DEPRECATED_NON_AUTHORITATIVE** — O9 simulation lane only; Paper fills route to `CanonicalPortfolio` |
| GOVERNED_FX | **COMPLETE_ENOUGH_FOR_FAIL_CLOSED_DERIVATIVE_SETTLEMENT** — per-currency buckets; no 1:1 fallback |
| CRYPTO_PAPER_READINESS | **AUDITED_SECONDARY** — not expanded in G13 |
| BROKER_MARGIN_MODEL | **NOT_GLOBALLY_AVAILABLE / EXPLICIT_FACTS_REQUIRED** |
| WAVE_7_SELECTOR_READINESS | **READY** — G13 closure criteria met; Wave 7 frontend work may begin (not started) |

## G13 artifacts

| Artifact | Role |
|---|---|
| `risk/margin_facts.py` | Margin requirement fact contract + admission |
| `portfolio/paper_fill.py` | Canonical Paper fill accounting |
| `tests/trading_correctness/test_g13_paper_derivatives.py` | 25 focused G13 regressions + performance evidence |
| `paper/preview.py` | `margin_facts_revision` preview binding (G13) |
| `paper/margin_resolution.py` | Fixture/explicit futures margin resolution for UI path |
| `portfolio/paper_adapter.py` | Multi-asset canonical snapshot projection |
| `artifacts/g13-runtime-performance.json` | Development-machine G13 timing evidence |

# P3.2 Unified Live Decision Workstation

**Date:** 2026-08-21  
**Status:** Active instrument drives live microstructure, research lane summaries, manual paper ticket, and evidence drill-down on `/workspace`.

## Architecture

`resolve_active_operator_instrument` remains canonical. `build_workspace_evidence_payload` composes thin lane adapters into a `WorkspaceEvidence` envelope without composite scores.

Flow:

```
active instrument
  → live market state (quote / trades / CVD / L2)
  → lane adapters (order flow, short intel, squeeze, market context, catalyst, whale, options, futures)
  → relevance / direction / quality / freshness (separate fields)
  → What Matters Now + evidence drawer
  → manual OrderTicket (research context informational only)
```

`RESEARCH_CONTEXT_EXECUTION_AUTHORITY = NONE`. Risk, execution admission, and paper authorization remain the only execution gates.

## API

`GET /workspace/{symbol}/evidence` — unified lane envelope + `what_matters_now` + `evidence_mix_summary`.

## UI closure

- Unified `WorkspacePage`: What Matters Now, live panel, paper ticket with context lanes, trace panel, evidence drawer.
- `ProviderHealthPanel`: channel health (quote / trades / L2), generation, quota, subscriptions.
- `ExecutionTracePanel`: expandable steps, broker order submitted = NO.
- Vite proxy bypass: HTML navigation to `/workspace` serves SPA; JSON API paths still proxy.

## Evidence semantics

- **Relevance** ≠ direction (HIGH relevance can be neutral or negative).
- Contradictions → `evidence_mix_summary = MIXED` (no vote / no % bullish).
- Missing lanes → `UNAVAILABLE` / `NOT_CONFIGURED` (never coerced to 0 or neutral score).

## Validation

- `tests/platform/test_unified_workstation_p32.py` — instrument coherence, semantics, safety, replay.
- Prior P3.1 paper execution path unchanged.

## Known limitations

- Short intelligence fixture-backed for admitted symbols only; live FINRA not required for P3.2.
- Market context remains BOXL-scoped fixture lane for non-BOXL symbols.
- Options/futures explicit `NOT_CONFIGURED` / `NOT_APPLICABLE` when entitled sources absent.
- OpenD generation bounce: run `tools/moomoo/smoke_reconnect.py` with live env when OpenD available.

## Roadmap note

Next high-value milestone: **A. Decision Research / Strategy Synthesis** (governed combination research, manual orders only).

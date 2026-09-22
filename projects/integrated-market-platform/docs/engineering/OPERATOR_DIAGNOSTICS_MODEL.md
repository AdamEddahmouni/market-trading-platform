# Operator diagnostics model (Lane C)

**Status:** **MERGED** on `origin/main` @ `50a1477f` ([#289](https://github.com/AdamEddahmouni/market-trading-platform/pull/289)). Read-only HTTP surface; does not start collectors or calibrate Item 9.

**Related:** [STATE_PATH_OPERATOR_CONVENTION.md](STATE_PATH_OPERATOR_CONVENTION.md), [PROVIDER_READINESS.md](PROVIDER_READINESS.md), [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md), Control UI (`docs/ui-redesign-v2/pages/control.md`).

## Purpose

Answer sixteen operator questions without raw logs or secret material. The model **composes** existing endpoints and read-only libraries; it does not upgrade evidence classes or start collectors.

**Liveness ([#379](https://github.com/AdamEddahmouni/market-trading-platform/pull/379)):** a bound port is **not** HEALTHY. Inspect `GET /provider/health` (`service_liveness`) and this snapshot's `readiness_vs_liveness`. Existing tokens only (`HEALTHY` / `UNREADY` / `UNAVAILABLE` / `NOT_APPLICABLE`; `STALLED` unused). Transport-up without application progress is `UNREADY` (`TRANSPORT_UP_APPLICATION_NOT_PROGRESSED`). HTTP 200 on a listening port is not sufficient.

## Canonical API

```http
GET /operator/diagnostics
```

Capability: `state.read` (same as `/operator/readiness`). Response schema: `operator-diagnostics/1.0.0`.

### Example shape (no secrets)

```json
{
  "schema_version": "operator-diagnostics/1.0.0",
  "severity": "DEGRADED",
  "secrets_included": false,
  "operator_questions": {
    "q01_imp_running": { "answer": true, "detail": "HEALTHY" },
    "q02_runtime_git_sha": {
      "answer": "270ce2a6acdb…",
      "frozen_collector_pin": "fed2d9f7",
      "matches_frozen_authority": false
    }
  },
  "sections": {
    "lifecycle": { "status": "HEALTHY" },
    "runtime": {
      "item9_preflight": {
        "disposition": "WRONG_RUNTIME",
        "does_not_start_collector": true
      }
    }
  },
  "human_summary": [
    "API runtime SHA is not the frozen Item 9 collector authority…"
  ]
}
```

## Sixteen questions → sources

| # | Question | Primary source today | Gap |
|---|----------|---------------------|-----|
| 1 | Is IMP running? | `/operator/lifecycle/status` | API up ≠ lifecycle supervisor up if probed only via `/context` |
| 2 | Which SHA is running? | `resolve_runtime_git_sha` + item9 preflight | UI does not show SHA on Command by default |
| 3 | Which config is loaded? | `/operator/config` (masked) + `state_path_diagnostic` | Env vs file vs worktree split not one field |
| 4–5 | Providers healthy vs degraded? | `/operator/readiness` | Role/degradation impact is UI copy (Lane E) |
| 6 | Data fresh? | readiness `freshness` + `/provider/health` + `/opportunities/summary` | Live lag metrics gated on `IMP_LIVE_OBSERVATIONAL` |
| 7 | Session evidence class | Composed (idle/replay/simulation/research/empirical) | No single backend enum yet |
| 8–9 | Collector active? frozen `.imp-actual-01-phase-d` @ `fed2d9f7`? | item9 preflight | API omits process probe (`NOT_RUN`); tools CLI may show `COMPLETED` |
| 10–11 | Expected cycle fail? recovery? | **NOT_OBSERVED** | No cycle ledger exposed |
| 12 | Evidence missing vs unavailable vs invalid | Composed gaps list | Corpus/FTEP integrity not inlined (use CLI) |
| 13–16 | Allowed/forbidden/intervention/headline | Governance block + composed | Forbidden list is policy, not runtime enforcement |

## Sep 18 outage epoch `121031` (case study, no backfill)

Observed diagnostic gaps during the Sep 18 engineering window (treat `121031` as the operator epoch tag, not evidence to rewrite):

1. **Runtime vs collector conflation** — `origin/main` software SHA (`270ce2a…`) served APIs while governed Item 9 collection authority remained `fed2d9f7` on `.imp-actual-01-phase-d`. Preflight reported `WRONG_RUNTIME` (correct) but Control/lifecycle could still look “healthy.”
2. **State path split** — Linked worktrees with empty `.local` while canonical FTEP SQLite lived on the primary checkout (`WORKTREE_STATE_MISMATCH` from `imp.py state-path`).
3. **Process probe asymmetry** — `imp.py item9 next-rth-preflight` runs duplicate `--poll` detection; HTTP diagnostics intentionally pass `active_collector_probe=None` until Lane B injects a shared probe adapter.
4. **Feed vs platform health** — `/opportunities/summary` `UNREADY` / `LIVE_AS_OF_UNAVAILABLE` did not surface as a first-class platform severity alongside lifecycle `HEALTHY`.
5. **Secret-leak audit fragility** — Historical `UI_SECRET_LEAK_BLOCKED` on readiness/config blocked the very surfaces operators need (fixed on main for enum-shaped metadata).

This model elevates those failures into `severity`, `human_summary`, and `operator_questions` without mutating receipts or restarting collectors.

## Operator truth contract (Weekend Wave B — Lane E)

`GET /operator/diagnostics` schema `operator-diagnostics/1.1.0` adds backend-owned
`operator_truth` (`operator-truth/1.0.0`). Control must not remap these tokens.

| `by_id` | Meaning |
|---|---|
| `item9-corpus` | Calendar/methodology progress. **2/3 is `IDLE`, never `DEGRADED`.** |
| `imp-lifecycle` | Platform lifecycle |
| `operator-readiness` | Operator readiness |
| `item9-preflight` | Item 9 preflight disposition |
| `collector` | Prospective collector process probe |
| `live-execution` | Live real-money execution env |
| `expected-cycle` | Consumes `cycle_recovery.expected_cycle_failure` (Lane D parsers stay Lane D) |
| `evidence-gaps` | Composed gaps list |

Clock: `as_of_utc` + `as_of_clock_kind: wall_utc` (ISO-8601 wall clock). The payload
does **not** include `generated_at_monotonic`. Item 9 corpus exposes
`sample_gate_progress` and does **not** emit top-level `receipt_dir` (Lane E).

`sections.runtime.item9_corpus_status.progress_truth` is calendar/methodology state: **`2/3` → `IDLE`** (not platform `DEGRADED`); **`3/3` → `HEALTHY`** for the distinct-RTH-date floor only (still **not** `CALIBRATED`). Nested `report.receipt_dir` and `expected_cycle` host-absolute filesystem paths stay redacted or normalized to repo-relative / `.imp-actual-01-phase-d/…` form (#294).

Lane B (Control presentation) should consume `ui/src/api/operatorTruth.ts` instead of
re-deriving truth in `operatorDiagnosticsPresentation.ts`. Command KPIs should use
`data_quality.operator_surface_flag` (`OK` or `STALE_OR_DEGRADED`).

## Lane boundaries

| Lane | Owns | Lane C does not edit |
|------|------|----------------------|
| B | Provider clients, path resolvers, heartbeat/readiness backend, process probe, collector identity | `tools/provider_readiness.py`, `service_health.py`, item9 probe injection |
| E | Control/Command UI | `ui/src/components/control/*` |
| C | Diagnostic model, aggregator, schema/docs | — |

### Sequential integration after Lane B

1. Lane B exports `active_collector_probe` adapter callable from a stable module.
2. Lane C wires probe into `build_operator_diagnostics_snapshot` (keep default `NOT_RUN` in tests).
3. Lane B adds `expected_cycle_failure` / `recovery_observed` tokens to lifecycle or heartbeat receipts.
4. Control consumes `GET /operator/diagnostics` via `OperatorDiagnosticsSchema` and `ui/src/api/operatorTruth.ts` (do not re-infer Item 9 2/3 as DEGRADED).
5. `preferItem9OperatorTruth` keeps calendar-incomplete local IDLE when backend says DEGRADED. Live OFF remains Control POLICY — not remapped from backend `live-execution`. `NOT CALIBRATED` / `CALIBRATION FORBIDDEN` stay presentation tokens.

## Evidence integrity

- Never upgrade historical/replay/simulation into prospective empirical.
- `does_not_start_collector: true` on item9 preflight section.
- Forbidden actions list includes collector restart, receipt mutation, calibration auto-fit, live execution.

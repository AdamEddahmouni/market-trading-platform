# Paper Forward-Testing Bridge

**Status:** Accepted — professor-directed post-G15 product increment

## Purpose

Connect governed research/strategy decisions to **prospective Paper evaluation** without look-ahead leakage, Live execution, or bypass of the existing Paper order lifecycle.

This is **not** backtesting, **not** Live trading, and **not** autonomous execution.

```text
research/strategy decision
  → time-locked forward-test decision (DRAFT → LOCKED)
  → governed Paper lifecycle (EXECUTION mode only, optional)
  → subsequent market observations (append-only)
  → forward-test outcome (signal vs execution separated)
  → evidence / metrics / review
```

Package: `src/market_platform_foundation/intelligence/paper_forward_bridge/`

## Relationship to BUILD 26 / BUILD 27

| Layer | Role |
| --- | --- |
| BUILD 26 forward qualification | Forecast shadow evidence program |
| BUILD 27 paper execution qualification | Paper execution evidence program |
| **Paper forward-testing bridge** | Product path from strategy evaluation → governed Paper forward test |

The bridge reuses Paper execution governance and decision-source snapshots; it does not replace qualification runners.

## Domain model

### ForwardTestSession

Groups forward tests under one strategy/universe/horizon configuration.

### ForwardTestDecision

Canonical prospective record with explicit `run_kind=FORWARD_TEST` (never `BACKTEST`).

Key fields:

- `decision_time_ns`, `source_time_ns`
- immutable `decision_payload` after lock
- append-only `observations`
- separate `signal_outcome` and `execution_outcome`
- optional `paper_order_id` / `paper_intent_id` linkage

## Lifecycle

```text
DRAFT → LOCKED → [PAPER_SUBMITTED → PAPER_ACTIVE →] OBSERVING → EVALUABLE → EVALUATED
```

Exceptional: `REJECTED`, `CANCELLED`, `EXPIRED`, `INVALID`, `INSUFFICIENT_DATA`

`SIGNAL_ONLY` tests skip Paper submission and move `LOCKED → OBSERVING` directly.

## Time integrity

| Time | Meaning |
| --- | --- |
| `decision_time_ns` | When IMP recorded the forward decision |
| `source_time_ns` | Latest legitimate input source time at decision |
| observation `source_time_ns` | Provider/source time of appended evidence |
| evaluation time | After `decision_time_ns + evaluation_horizon_ns` |

Safeguards (`temporal.py`):

1. future `source_time` rejected at decision creation
2. decision payload immutable after lock
3. observations cannot precede decision time
4. evaluation blocked before horizon
5. `run_kind` must be `FORWARD_TEST`

## Paper execution integration

Execution-capable tests (`test_mode=EXECUTION`) build a governed preview/submit body via `paper_handoff.py`:

- passes through `preview_paper_order` / `submit_paper_order`
- uses `decision_source_snapshot` type `forward_test_decision`
- correlation id `forward_test:{forward_test_id}`
- duplicate Paper submission blocked at store level

Paper remains Paper. Live adapters are unreachable from this path.

## Account isolation

All records are scoped by `account_id`. API and service layers reject cross-account access.

Frontend query key: `paperForwardTests(accountId)`.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/paper/forward-tests` | List decisions |
| GET | `/paper/forward-tests/{id}` | Detail |
| GET | `/paper/forward-tests/sessions` | List sessions |
| GET | `/paper/forward-tests/{session_id}/summary` | Session aggregate |
| POST | `/paper/forward-tests/sessions` | Create session |
| POST | `/paper/forward-tests/decisions` | Create decision |
| POST | `/paper/forward-tests/lock` | Lock decision |
| POST | `/paper/forward-tests/submit` | Submit to Paper or enter observing |
| POST | `/paper/forward-tests/observe` | Append observation |
| POST | `/paper/forward-tests/evaluate` | Evaluate eligible decision |

## UI surface

Paper Workspace exposes `PaperForwardTestPanel` with explicit **PAPER** / **Forward Test** labeling and pending/evaluated/rejected states.

## Outcome metrics

### Signal quality

- entry/exit reference prices from observations
- absolute and percentage return
- directional correctness (when direction is non-neutral)

### Execution quality (EXECUTION mode only)

- Paper order/intent linkage
- fill count / PnL placeholders (when available from Paper lifecycle)

Metrics are never conflated in a single score.

## Forward test vs backtest

`run_kind=FORWARD_TEST` is required. Historical replay/backtest results must not use this bridge.

## Failure semantics

Failures are explicit: insufficient data, horizon not reached, Paper rejection, account mismatch, duplicate submission, temporal violations.

## Testing

Primary suite: `tests/intelligence/test_paper_forward_bridge.py`

Activation suite: `tests/intelligence/test_forward_test_activation.py`

Protocol ref suite: `tests/intelligence/test_forward_test_protocol_ref.py`

Preflight API suite: `tests/intelligence/test_forward_test_preflight_api.py`

Persistence suite: `tests/intelligence/test_forward_test_persistence.py`

UI model tests: `ui/src/components/paper-workspace/buildForwardTestPanelModel.test.ts`

## FTEP-V1 activation (campaign governance)

Empirical Paper forward-test sessions require a **frozen activation manifest**
under `artifacts/forward-test-campaigns/<campaign_slug>/ACTIVATION_MANIFEST.json`.

| Module | Role |
| --- | --- |
| `activation.py` | Load/validate manifest, SHA-256 fingerprint, freeze state machine |
| `protocol_ref.py` | Verify `PROTOCOL_REF.json` doc hash against preregistered protocol |
| `campaign_binding.py` | One ACTIVE campaign per account; durable binding at session create |
| `preflight.py` | Deterministic preflight (`READY` / `NOT_READY`) before session create |
| `session_policy.py` | Launch-policy gates: calendar/RTH, phase transition, overlap, cohort, evidence class, eval force |
| `service.py` | Gates `create_session`; binds manifest fields; validates decisions |

Preflight enforces: Paper-only, `FORWARD_TEST`, manifest `FROZEN`/`ACTIVE`, fingerprint
match, protocol reference hash, persistence when required, cohort-arm policy binding.
Campaign binding enforces one ACTIVE campaign per account (`forward_test_campaign_bindings`).
API preflight: `GET /paper/forward-tests/preflight?campaign_slug=...&account_id=...`.
Freeze tooling: `python tools/forward_test/freeze_activation_manifest.py <campaign_slug> --frozen-at ...`.
Non-campaign session create is rejected unless `IMP_FORWARD_TEST_CAMPAIGN_REQUIRED=0`.
Empirical paths (`lock`, `submit`, `observe`, `evaluate`) require a campaign-bound session.

Session fields added: `campaign_id`, `protocol_id`, `activation_version`,
`manifest_fingerprint`, `cohort_arm`, `config_frozen`.

Decision fields added: `evidence_class` (default `UNCLASSIFIED`; no auto-promotion to
empirical classes), `cohort_arm`.

Launch-policy enforcement (`session_policy.py`): when `calendar_scope` is set on the
manifest, decision/lock times must fall inside US equity RTH (09:30–16:00 ET); phased
`SIGNAL_ONLY` → `EXECUTION` requires `phase_transition_min_locks` integrity-clean locks;
`overlap_policy=FORBID_CONCURRENT` blocks overlapping open decisions per symbol;
empirical `evidence_class` values are rejected at create/lock; campaign-bound
`evaluate(..., force=True)` is forbidden unless `IMP_FORWARD_TEST_EVAL_FORCE=1` (test
override only). Sample floors in the manifest gate statistical disposition only, not
individual locks.

See [FTEP-V1_OWNER_DECISION_PACKET.md](../engineering/FTEP-V1_OWNER_DECISION_PACKET.md).

## Persistence (PD-09)

When `IMP_PERSIST_STATE=1` or `IMP_STATE_DIR` is set, forward-test sessions,
decisions, append-only observations, and idempotency claims are stored in the
local SQLite state database (`local_state`, schema v6) alongside the Paper
ledger. Restart recovery reopens the same account-scoped records; locked
decision fields remain immutable; duplicate Paper submission and evaluation
claims survive restart. Schema v6 adds transactional multi-row writes,
distinct persist/available/receive clocks, git SHA + simulator version on
runs, campaign/strategy/instrument query filters, unique operator acks, and
a reconstruction API that joins Paper ledger fills/PnL without scraping logs.
When a decision payload includes structured `freshness` evidence, reconstruction
surfaces it on the decision row. PD-09 (PR #18) remains COMPLETE; v6 is a later increment on the same store.

Signal identity is persisted in `forward_test_signal_links` when
`decision_payload.opportunity_id` is set (`INSERT OR IGNORE`). The link
survives close/reopen; reconstruction exposes `opportunity_id` /
`signal_id` / `paper_order_id` / ledger PnL. Full `OpportunityV1` records
remain in the intelligence repository — they are not a second campaign
store.

Operator watch/review/dismiss acknowledgements:

- Persist-on: unique `opportunity_operator_acks` rows. Survive restart.
- Persist-off: process-local memory only (`INTENTIONAL_EPHEMERAL`).
  Durable acks with persistence disabled are `NOT_APPLICABLE` — they
  would require a second store. Campaigns with `persistence_required`
  are preflight-blocked (`PERSISTENCE_DISABLED`).

Factory: `create_forward_test_repository()` in
`paper_forward_bridge/repository.py` (in-memory when persistence is off).

Path A prospective hop (`PathAProspectiveComposer`): Paper/Demo CLI
`tools/path_a_prospective_run.py` does not pre-build the invoke before fetch.
Composer fetches once (OpenD primary via `primary_equity_quote_provider()`),
G7 remains freshness authority, and auto-builds `PathAScanCaller` with the
admitted `quote_event` so `path_a_status` is honest `EMPTY` when no MATCHED
strategy (not null) and the catalog is not stuck on
`FCAST_NO_QUOTE_OBSERVATION`. Yahoo delayed is overlay-only and is not
swapped in when OpenD is down. G7 capability/selection registers hop L1
identity `moomoo.opend.observational` (`US_EQUITY_L1`); Yahoo remains
unknown as hop L1. Unstamped OpenD fail-closes (`PROVIDER_DOWN`) until a hop
stamps health after an admitted fetch. The hop CLI calls `diagnose_opend(start=True)`
before quote fetch so an installed local OpenD can be started; if it is
still down the outcome is
`PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE` (or
`MOOMOO_SDK_MISSING` if loopback TCP answers but the vendor SDK is
absent). Hop JSON includes Finviz Elite `equity_context` as a screening/news
overlay classifier (fail-closed `NOT_CONFIGURED` without a token; never hop L1).
After `python tools/imp.py env install-opend`, hop uses the IMP
`.venv` only (`PYTHONPATH=src`); do not mix `moomoo-api-test` site-packages.
`--preregistration-path`
may point at a previously persisted Phase-6 record; create is a separate
operator step (`persist_paper_demo_preregistration`) that stamps `registered_at`
before any hop. Load requires identity match and `registered_at` before quote
`event_time_ns`. `--forecast-path` may point at a previously persisted
PRODUCTION `ForecastV1`; load requires identity/PIT/champion/horizon/account/mode
to match Opportunity Engine hop policy; otherwise `FORECAST_UNAVAILABLE`.
Create is a separate operator step (`produce_paper_demo_forecast`) that
persists only a BUILD 14 `EMITTED_CALIBRATED` artifact; CONTROL, RESEARCH,
IDENTITY_CONTROL, and uncalibrated output are not written. The hop does not
mint a probability. Software producer wiring is not FTEP `EMPIRICAL_ACTIVE`.
Catalog evaluators never mint a preregistration. A scanner
MATCHED with no eligible loaded forecast is `FORECAST_UNAVAILABLE`,
not OE EMIT. Honest EMPTY does not
enter the MATCHED loop or call Opportunity Engine. A Paper/Demo MATCHED
test fixture does call `bridge_strategy_match_to_opportunity` →
`OpportunityEngine.assess`. If G7 fail-closes, overall status stays
`G7_NOT_ACTIONABLE` even when Path A is `MINTED`. That fixture is not an
empirical MATCHED hop. After a Paper **MINTED**
result, optional v6 write uses the existing `ForwardTestService.create_decision`
API with G7 `freshness` in `decision_payload_json` (and `forward_test_signal_links`
when `opportunity_id` is set). Requires an existing Paper FT session — Path A
does not auto-activate FTEP. `tools/path_a_prospective_run.py` can inject that
session's `PathAPersistContext` via `--persist-account-id`/`--persist-session-id`/
`--persist-strategy-id`/`--persist-strategy-version`, but only when the
existing `IMP_STATE_DIR`/`IMP_PERSIST_STATE` persist-on switch is already set
and every identifier is supplied; the CLI never creates, freezes, or
activates a campaign/session itself, so an operator must create the session
out-of-band (e.g. `tools/ftep_session_start.py`) first. Persist-off minted
decisions stay `INTENTIONAL_EPHEMERAL` (no second store). Demo MINTED does
not write FT rows (`FORWARD_TEST_PAPER_MODE_REQUIRED`). Live never mints.
Reconstruction after restart is the PD-09 path; fills are not fabricated.

## Known limitations

- Durable storage is local SQLite only (no MongoDB / remote campaign DB)
- Outcome metrics use observation payloads, not live provider polling
- **Observational live news ingress** is implemented as opt-in scaffolding only
  (`market_platform_foundation/news/observational_ingress.py`). It requires
  `IMP_OBSERVATIONAL_NEWS_INGRESS=1` plus per-provider `IMP_NEWSAPI_LIVE` /
  `IMP_FINNHUB_LIVE` gates, normalizes through `aggregator_bridge`, and is
  **not** auto-wired into forward-test `observe` paths or Paper submission.
  FTEP-V1 campaign connectivity remains deferred under manifest
  `deferred_until_evidence` (`FTEP-ACT-04`, `FTEP-D038`). Operator-local
  bounded probes: [OPERATOR_PROBE_RUNBOOK.md](../engineering/OPERATOR_PROBE_RUNBOOK.md)
  §5–6.
- EVIDENCE-01B campaign auto-bridge not wired
- Route-policy fixes for forward-test UI mutations remain follow-up work

## Professor-facing summary

1. **What is forward tested?** Locked strategy/research decisions under a declared horizon.
2. **Why prospective?** Decisions are frozen before later observations and evaluation.
3. **Look-ahead prevention?** Source-time guards + immutable payload + append-only observations.
4. **Frozen at decision time?** `decision_payload`, provenance snapshot, direction, strategy version.
5. **What happens later?** Observations accumulate; evaluation runs after horizon.
6. **Paper execution?** Optional governed preview/submit through existing Paper API.
7. **Metrics?** Separate signal and execution outcome blocks.
8. **Vs backtests?** Explicit `FORWARD_TEST` run kind; backtest boundary regression tested.
9. **Auditability?** Provenance snapshot + immutable decision payload + observation trail.
10. **Future work?** EVIDENCE-01C integration, richer execution PnL linkage, remote campaign sync.

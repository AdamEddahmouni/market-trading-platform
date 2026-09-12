# FTEP-V1 Activation Blocker Report

**Classification:** `CURRENT_ENGINEERING_TRUTH`  
**Established:** 2026-09-12  
**Branch:** `work/ftep-v1-activation`  
**Machine-readable audit:** [artifacts/ftep-v1-activation-goal-audit.json](../../artifacts/ftep-v1-activation-goal-audit.json)  
**Executive closure:** [artifacts/wave-b-closure-report.json](../../artifacts/wave-b-closure-report.json)

## Executive disposition

**IMPLEMENTATION_OBJECTIVE_COMPLETE** — Section 28 success criteria **A–Z**: **26/26 MET** with per-criterion `implementation_disposition: IMPLEMENTATION_COMPLETE` (see goal audit). Observational ingress scaffold landed in **`437cd1c`**; campaign ACT-04 wire remains governance-deferred. Qualifying **FTEP-V1-001 / ES-news** empirical activation is **out of scope** for this engineering goal and remains **not authorized**. **implementation_objective_complete:** `true`; **qualifying_activation_out_of_scope:** `true`.

Do **not** freeze the activation manifest until owner decisions, calibration numerics, and probes are resolved.

## Consolidated blockers

| Blocker ID | Owner | Type | Why it blocks qualifying activation | Next action |
|------------|-------|------|-------------------------------------|-------------|
| OWNER-OD-1-11 | Owner | Human decision | Activation manifest fields and campaign policy choices unresolved | Complete [FTEP-V1_OWNER_DECISION_PACKET.md](./FTEP-V1_OWNER_DECISION_PACKET.md); record in manifest |
| OWNER-CALIBRATION-THRESHOLDS | Owner | Human decision | Numeric calibration gates UNSET per [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md) | Preregister campaign-specific thresholds; bind in manifest |
| PROBE-MOOMOO | Operator | Local probe | ES futures quote entitlement stale; OpenD refresh required | Run non-destructive Moomoo probe; update capability snapshot |
| EXT-MOOMOO-FUTURES-ENTITLEMENT | External | Entitlement | `US_FUTURES_QUOTE` not evidenced for campaign PRIMARY_MARKET_EVIDENCE | Verify account/plan; refresh evidence artifact |
| PROBE-FINVIZ | Operator | Local probe | Finviz live_session not configured in repo evidence | Configure safely; probe; update matrix |
| PROBE-G-A5-BROKER-CANDIDATES | Operator | Local probe | Alpaca/Tradier comparator state not freshly verified | Run broker audit probes per [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md) |
| EXT-PREMIUM-WIRES | External | Provider | No operational Reuters/DJ/Benzinga-class wire in repo | Select provider + terms if campaign requires premium headlines |
| EXT-NEWSAPI-FINNHUB-PIT | External | Data rights | Bounded live windows; not historical PIT archive for ES/news claims | Do not claim PIT news archive without new source |
| DEFER-FTEP-ACT-04-OBS-INGRESS | Owner/Engineering | Governance deferral | Live observational news ingress intentionally deferred (FTEP-D038) | Re-open only if manifest de-defers ACT-04 |
| DEFER-FTEP-ACT-06 | Engineering | Deferred scope | EVIDENCE-01B auto-bridge to forward path | Track in reconciliation-gate; not required for offline Wave B closure |

## Safe operator sequence (after blockers)

1. Resolve **OWNER-OD-1-11** and **OWNER-CALIBRATION-THRESHOLDS**.
2. Run **PROBE-*** commands per [OPERATOR_PROBE_RUNBOOK.md](./OPERATOR_PROBE_RUNBOOK.md); regenerate `artifacts/wave-a-findings/capability-matrix-snapshot.json`.
3. `python tools/imp.py providers campaign-readiness FTEP-V1-001 --json` — must fail closed until gaps clear.
4. `python tools/forward_test/freeze_activation_manifest.py` — only when manifest complete.
5. Shakedown segment per gates G-A20; qualifying cohort only after freeze.

## Explicit prohibited claims

Do **not** state or imply:

- FTEP-V1-001 is **active**, **frozen**, or collecting **qualifying prospective** evidence.
- **CONNECTED** implies **ENTITLED**, **CAPABILITY_VERIFIED**, or **CAMPAIGN_SUITABLE**.
- Internal Paper simulator or external Paper broker fills are **market truth**.
- Fixture/replay or `RECORDED_ARTIFACTS_ONLY` paths constitute **prospective market validation**.
- ES/news campaign has **verified lawful live** headline or futures streams without dated probe artifacts.
- **Live trading authority** is enabled (LIVE-001 remains blocked).
- Owner decisions **OD-1–OD-11** are resolved without signed manifest evidence.
- Universal calibration acceptance numbers exist without owner preregistration.
- Notion or external systems were updated unless actually performed in that environment.

## Allowed claims (with evidence)

- Wave B **engineering packages** (capability matrix, gap engine, campaign-readiness, calibration schema, snapshot-compare, CG/news bridges) are implemented and covered by tests.
- **Immutable freeze tooling** exists; manifest is **not** frozen.
- Smallest ES/news stack and deficiencies are documented in [es-news-provider-stack-selection.json](../../artifacts/ftep-v1-001/es-news-provider-stack-selection.json).
- `python tools/imp.py validate fast` and prior full **closure** runs passed on this branch (see wave-b-closure-report).

## Automatable gaps still in repository

| Gap | Automatable? | Notes |
|-----|----------------|-------|
| PIT-A-001 unified export API | **Closed** (`research/pit_export.py`) | Durable store (PIT-A-005) still open |
| DEFER-UNIFIED-UI-MATRIX | Yes, deferred | Acceptable deferral per wave-b |
| DEFER-FTEP-ACT-04 observational ingress | Yes, when governance opens | Currently owner-gated deferral |
| Local probes / entitlements / owner packet | **No** | Operator + owner + external providers |

**Conclusion:** No remaining **activation-critical** engineering gap is unimplemented except items **explicitly deferred** or requiring **human/external** action. Further repo work without probes and owner decisions would not truthfully advance qualifying activation.

## Related documentation

- [FTEP_ACTIVATION_GATES.md](./FTEP_ACTIVATION_GATES.md)
- [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md)
- [artifacts/wave-a-findings/reconciliation-gate.json](../../artifacts/wave-a-findings/reconciliation-gate.json)

# FTEP-V1 Activation Blocker Report

| Field | Value |
| --- | --- |
| **Classification** | `CURRENT_ENGINEERING_TRUTH` |
| **Established** | 2026-09-12 |
| **Last verified** | 2026-09-13 against `origin/main@9cb541c` (PR #40) |
| **Machine-readable audit** | [artifacts/ftep-v1-activation-goal-audit.json](../../artifacts/ftep-v1-activation-goal-audit.json) (historical Wave B closure) |
| **Executive closure** | [artifacts/wave-b-closure-report.json](../../artifacts/wave-b-closure-report.json) (historical) |
| **Current campaign labels** | [FTEP_CAMPAIGN_CATALOG.md](FTEP_CAMPAIGN_CATALOG.md) |

## Executive disposition

Wave B **implementation** packages remain complete (capability matrix, gap engine, campaign-readiness, freeze tooling, integrity). That is **not** campaign activation.

Program decision: **`FTEP_EMPIRICAL_NOT_READY`**. Not `EMPIRICAL_ACTIVE`. Live off.

**FTEP-V1-001** is **`MANIFEST_FROZEN`** (fingerprint invariant `69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C`). OD-1…OD-11 are recorded in the frozen manifest (OD-11 pathway **A** = bind/freeze/preflight only). Prospective disposition is **`FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`**. SIGNAL_ONLY is **not** authorized. **Not** `FROZEN_FOR_ACTIVATION`. **Not** `EMPIRICAL_ACTIVE`. **Do not mutate** the frozen JSON, OD fields, universe, or fingerprint.

**FTEP-V1-002** is **`MANIFEST_FROZEN` + `SIGNAL_ONLY_AUTHORIZED`** via committed receipts. Governed sessions **0**. **Not** `EMPIRICAL_ACTIVE`. Does **not** unblock V1-001.

Remaining blockers for a lawful first qualifying observation are **entitlement**, **authorization B**, **campaign-readiness READY**, **dated ES contract**, and **calibration/execution** — not “the manifest is not frozen.”

Open **IMPLEMENTED** drafts (not merged, not empirical activity): [PR #41](https://github.com/AdamEddahmouni/market-trading-platform/pull/41) calibration harness (head `7f7e63b`; CI green; simulator **not** `CALIBRATED`; Tradier sandbox token empirically **ABSENT**); [PR #42](https://github.com/AdamEddahmouni/market-trading-platform/pull/42) quote→admission→G7→Path A hop (head `df2b66c`; honest `EMPTY`; persist CLI lives on stacked [#45](https://github.com/AdamEddahmouni/market-trading-platform/pull/45)). Operator OpenD hop on [#50](https://github.com/AdamEddahmouni/market-trading-platform/pull/50) `2c9a4e4`: AAPL `last_price=332.27`, `G7_NOT_ACTIONABLE` (Sunday). Finviz Elite overlay empirically `FETCHED` on [#54](https://github.com/AdamEddahmouni/market-trading-platform/pull/54) (`LIVE_DISABLED`) but **not** in Path A hop CLI JSON. No PRODUCTION `ForecastV1` contributor JSON in-repo. Live remains forbidden.

## Consolidated blockers

| Blocker ID | Owner | Type | Why it blocks qualifying activation | Next action |
|------------|-------|------|-------------------------------------|-------------|
| OWNER-OD-1-11 | Owner | **Closed for this freeze** | OD-1…OD-11 recorded in frozen V1-001 JSON (pathway A). Freeze-of-fields is done. | Do **not** re-open freeze. Session/lock authorization is a **separate** receipt (pathway B). |
| FROZEN-V1-001-DO-NOT-MUTATE | Engineering | Integrity | Fingerprint `69C36BA…` is invariant. Catalog + glossary win over the frozen JSON `classification` string that misuses `FROZEN_FOR_ACTIVATION`. | Append-only receipts / new campaign version only. Never rewrite frozen JSON. |
| AUTH-SIGNAL-ONLY-B | Owner | Authorization | Frozen attestation `signal_only_session_authorized: false`. No V1-001 SIGNAL_ONLY receipt. Pathway A does not authorize sessions. | Append-only SIGNAL_ONLY receipt after ES gaps clear. Do not flip frozen `operator_attestation`. |
| OWNER-CALIBRATION-THRESHOLDS | Owner | Human decision | Numeric calibration gates **UNSET/BLOCKING** per [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md). Simulator **not** `CALIBRATED`. | Preregister campaign-specific thresholds from a declared-scope cohort. Draft harness: PR #41 (not merged; not calibrated). |
| PROBE-MOOMOO | Operator | Local probe | Last dated **ES** quote probe (2026-09-12) **NOT_ENTITLED**. Cloud VM has no OpenD. An operator-machine **equity** hop on [#50](https://github.com/AdamEddahmouni/market-trading-platform/pull/50) `2c9a4e4` admitted AAPL `last_price=332.27` (`G7_NOT_ACTIONABLE`, Sunday stale) — that is **not** ES entitlement and does **not** close G-A6/G-A7. | Run non-destructive Moomoo **ES** probe on an operator machine; do not substitute IBKR delayed L1 or V1-002 equity L1. |
| EXT-MOOMOO-FUTURES-ENTITLEMENT | External | Entitlement | `US_FUTURES_QUOTE` not evidenced for campaign PRIMARY_MARKET_EVIDENCE. Executable: `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`. | Verify account/plan; refresh evidence artifact. Closing equity L1 CAMPAIGN_BOUND **does not** close ES G-A6/G-A7. |
| G-A6-ES-AUTHORITY | Engineering / Owner | Coverage gap | Live campaign-readiness still reports `COVERAGE_GAP:G-A6` / `G_A6_CAMPAIGN_BOUND_MISSING` for ES. V1-001 has no `market_data_bindings`. | Bind ES market-data authority CAMPAIGN_BOUND. Equity overlay is not ES G-A6. |
| G-A11-DATED-CONTRACT | Owner | Campaign binding | Universe is symbol `ES` only — not an executable dated contract month. | New campaign version if a dated key must be bound. Do not silent-edit frozen JSON. |
| PROBE-FINVIZ | Operator | Local probe | Cloud Finviz names **ABSENT**. Operator overlay empirically `FETCHED` on [#54](https://github.com/AdamEddahmouni/market-trading-platform/pull/54) (`LIVE_DISABLED`) but **not** in Path A hop CLI JSON. `NEWS_EXPORT` CONTEXT_ONLY is not ES quote. | Do not treat overlay `FETCHED` as hop L1 or as ES news. Live news ingress remains deferred (WAVE-A-002 / FTEP-ACT-04). |
| PROBE-G-A5-BROKER-CANDIDATES | Operator | Local probe | No usable Paper/sandbox comparator (`COMPARATOR_NOT_CONFIGURED` on PR #41). Tradier sandbox token empirically **ABSENT** on the operator machine. | Ready runner exists on PR #41; do not fabricate fills. Alpaca remains Phase 0 prohibited. |
| EXT-PREMIUM-WIRES | External | Provider | No operational Reuters/DJ/Benzinga-class wire in repo | Select provider + terms if campaign requires premium headlines |
| EXT-NEWSAPI-FINNHUB-PIT | External | Data rights | Bounded live windows; not historical PIT archive for ES/news claims | Do not claim PIT news archive without new source |
| DEFER-FTEP-ACT-04-OBS-INGRESS | Owner/Engineering | Governance deferral | Live observational news ingress intentionally deferred (FTEP-D038) | Re-open only if a **new** campaign version de-defers ACT-04 |
| DEFER-FTEP-ACT-06 | Engineering | Deferred scope | EVIDENCE-01B auto-bridge to forward path | Track in reconciliation-gate; not required for offline Wave B closure |

## Safe operator sequence (after remaining blockers)

1. **Do not mutate** frozen V1-001 JSON / fingerprint. OD-1–11 are already recorded.
2. Close **ES** G-A5/G-A6/G-A7 (entitled `US_FUTURES_QUOTE` ≥ `SAMPLE_VERIFIED` + campaign-bound ES capability contract). IBKR delayed L1 / CME-not-in-tree / fixtures / V1-002 L1 **do not** count.
3. Bind **dated ES contract month** (G-A11) via a **new** campaign version if needed.
4. Owner **SIGNAL_ONLY** authorization as an **append-only receipt** (pathway B). Frozen attestation stays `false`.
5. `python3 tools/imp.py providers campaign-readiness FTEP-V1-001 --json` — must be `READY` on the **session** host (`IMP_PERSIST_STATE=1` or `IMP_STATE_DIR`; coverage gaps cleared).
6. Integrity PASS; V1-001 fingerprint unchanged; `US_EQUITY_RTH` open; `ftep session-start` succeeds → then and only then `EMPIRICAL_ACTIVE`.

Until a governed prospective session starts, the label stays **`FTEP_EMPIRICAL_NOT_READY`** / **not** `EMPIRICAL_ACTIVE`.

## Explicit prohibited claims

Do **not** state or imply:

- FTEP-V1-001 is `FROZEN_FOR_ACTIVATION`, `SIGNAL_ONLY_AUTHORIZED`, `EMPIRICAL_ACTIVE`, or collecting qualifying **`ACTUAL_FORWARD`** evidence.
- The V1-001 manifest is **not** frozen (it **is** `MANIFEST_FROZEN`; freeze ≠ activation).
- V1-002 authorization, Path A, G7, persistence schema, calibration harness, or delayed Yahoo overlay **unblocks** V1-001 or counts as `EMPIRICAL_ACTIVE`.
- **CONNECTED** implies **ENTITLED**, **CAPABILITY_VERIFIED**, or **CAMPAIGN_SUITABLE**.
- Internal Paper simulator or external Paper broker fills are **market truth** or `CALIBRATED`.
- Fixture/replay or `RECORDED_ARTIFACTS_ONLY` paths constitute **prospective market validation**.
- ES/news campaign has **verified lawful live** headline or futures streams without dated entitled-probe artifacts.
- **Live trading authority** is enabled (`LIVE-001` remains blocked).
- Owner decisions **OD-1–OD-11** are still unresolved (they are recorded; session authorization is a separate remaining gate).
- Universal calibration acceptance numbers exist without owner preregistration.
- Notion or external systems were updated unless actually performed in that environment.
- Open drafts **#41** / **#42** are merged or empirically observed.

## Allowed claims (with evidence)

- Wave B **engineering packages** (capability matrix, gap engine, campaign-readiness, calibration schema, snapshot-compare, CG/news bridges) are implemented and covered by tests.
- **Immutable freeze tooling** exists; **V1-001 and V1-002 manifests are frozen**. V1-001 is entitlement-blocked and not session-authorized. V1-002 is SIGNAL_ONLY-authorized with **0** sessions.
- Smallest ES/news stack and deficiencies are documented in [es-news-provider-stack-selection.json](../../artifacts/ftep-v1-001/es-news-provider-stack-selection.json) (`overall_disposition: BLOCKED`).
- `python3 tools/imp.py validate fast` and prior full **closure** runs passed on the Wave B branch (see wave-b-closure-report). Last green **main** is the #40 merge.
- PR #41 / PR #42 (and stacked OpenD/Finviz/Path A drafts) are **IMPLEMENTED** drafts: not merged, not `CALIBRATED`, not `EMPIRICAL_ACTIVE`. Overlay `FETCHED` and the Sunday OpenD AAPL print do **not** start a governed session.

## Automatable gaps still in repository

| Gap | Automatable? | Notes |
|-----|----------------|-------|
| PIT-A-001 unified export API | **Closed** (`research/pit_export.py`) | Durable store (PIT-A-005) still open |
| DEFER-UNIFIED-UI-MATRIX | Yes, deferred | Acceptable deferral per wave-b |
| DEFER-FTEP-ACT-04 observational ingress | Yes, when governance opens | Currently owner-gated deferral |
| Local probes / entitlements / SIGNAL_ONLY receipt | **No** | Operator + owner + external providers |
| Numeric calibration thresholds | **No** until owner freeze | Harness exists on draft PR #41; not `CALIBRATED` |

**Conclusion:** Qualifying activation is **not** waiting on “freeze the manifest.” V1-001 is frozen and entitlement-blocked. Further repo work without entitled ES data, authorization B, and a started governed session would not truthfully advance `EMPIRICAL_ACTIVE`.

## Related documentation

- [FTEP_ACTIVATION_GATES.md](./FTEP_ACTIVATION_GATES.md)
- [FTEP_CAMPAIGN_CATALOG.md](./FTEP_CAMPAIGN_CATALOG.md)
- [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md)
- [artifacts/wave-a-findings/reconciliation-gate.json](../../artifacts/wave-a-findings/reconciliation-gate.json)

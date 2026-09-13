# Provider activation increment (Wave B closure)

**Status:** `CURRENT_ENGINEERING_GUIDE`  
**Scope:** Post–Wave A prerequisite implementation (packages 1–3 + bridge/news), without manifest freeze, Live trading, or qualifying empirical evidence.

This document complements [PROVIDER_READINESS.md](./PROVIDER_READINESS.md) (operator commands) and the architecture contracts it references.

## Capability matrix

Machine-readable provider capability records align to [MARKET_DATA_CAPABILITY_CONTRACT.md](../architecture/MARKET_DATA_CAPABILITY_CONTRACT.md) promotion states (`CATALOGED`, `SAMPLE_VERIFIED`, `PROMOTED`, etc.).

| Command | Purpose |
| --- | --- |
| `python tools/providers/capability_matrix.py` | Emit deterministic snapshot to stdout |
| `python tools/providers/capability_matrix.py --output artifacts/wave-a-findings/capability-matrix-snapshot.json` | Write + schema-validate snapshot |
| `python tools/provider_readiness.py audit --json` | Merge matrix with value-blind gate rows (stale evidence as-of, capability contract IDs) |

Wave A inventory JSON under `artifacts/wave-a-findings/` remains the static reconciliation source; the matrix builder merges those artifacts with optional `provider_readiness` rows.

## Audit and readiness commands

```powershell
python tools/imp.py providers capability-matrix
python tools/imp.py providers audit --json
python tools/imp.py providers gaps --profile FTEP-V1-001 --json
python tools/imp.py providers campaign-readiness FTEP-V1-001 --json
```

Equivalent direct entry points remain under `tools/provider_readiness.py` and
`tools/providers/capability_matrix.py`.

- **audit** — capability contract IDs, entitlement reachability labels, stale evidence timestamps (no secret values).
- **gaps** — deterministic disposition of Wave A gap IDs (`WAVE-A-*`, `PIT-A-*`, `CG-*`, `CFG-*`) for a campaign profile.
- **campaign-readiness** — fail-closed composition of forward-test preflight + gap engine for an activation manifest slug.

## Gap engine

Implementation: `src/market_platform_foundation/providers/coverage_gap_engine.py`.

The engine aggregates campaign-scoped requirements (including activation gates **G-A6** / **G-A7**) against the capability-matrix snapshot. It does not perform live probes or mutate manifests.

## Campaign readiness evaluator

Implementation: `src/market_platform_foundation/intelligence/paper_forward_bridge/campaign_readiness.py`.

Composes `run_forward_test_preflight`, [FTEP_ACTIVATION_GATES.md](./FTEP_ACTIVATION_GATES.md), and gap-engine output for campaign profiles (**FTEP-V1-001** frozen ES-news; **FTEP-V1-002** proposed US-equity-news). A `NOT_READY` preflight result is expected while `activation_status` remains `PENDING_OWNER_DECISIONS` (V1-002) or while external entitlement gaps block V1-001 prospective collection.

```powershell
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

V1-002 readiness metadata includes `prospective_market_evidence` from dated Moomoo probe receipts (`moomoo_prospective_market_evidence.py`).

## Calibration and comparator semantics

Machine-readable hooks (package 3, commit `613a6b4`):

| Artifact / module | Role |
| --- | --- |
| `manifests/paper/schemas/calibration_thresholds.schema.json` | Threshold document shape; numeric acceptance values remain **UNSET** until owner/campaign freeze |
| `paper/calibration/comparator_contract.py` | Comparator binding contract per [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](../architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md) |
| `paper/calibration/futures_suitability.py` | ES/futures suitability gates for comparator selection (advisory, not procurement) |
| `paper/calibration/metrics.py` | Metric dimensions for calibration units (N, distributions, median, percentiles; fill/price/latency/partials/rejects/cancels) |
| `paper/calibration/pairing.py` | Correlation-id / pairing-table join of IMP vs comparator legs |
| `paper/calibration/persistence.py` | Append-only schema v6 `forward_test_observations` |
| `paper/calibration/runner.py` | Fail-closed classifier: `WAITING_FOR_MARKET` / `COMPARATOR_NOT_CONFIGURED` |
| `paper/calibration/asset_scope.py` | Equity Paper does not validate ES fills |
| `paper/calibration/thresholds.py` | Load/validate threshold payloads; fail closed when BLOCKING gates unset |

**Safe claim:** pairing/metrics/persistence harness exists; Tradier sandbox HTTPS is opt-in and production-blocked; execution-bearing numeric gates remain **BLOCKING/UNSET**.
**Prohibited claim:** simulator or external paper benchmark is calibrated; FTEP is `EMPIRICAL_ACTIVE`.

## Frozen provider snapshot comparison harness

Offline A/B style comparison for captured provider arms (latency, value disagreement, missingness):

| Command | Purpose |
| --- | --- |
| `python tools/providers/snapshot_compare.py tests/fixtures/providers/frozen_compare_sample.json` | Compare arms in a frozen JSON snapshot |
| Library: `market_platform_foundation.providers.snapshot_compare` | Reuse in probes and tests |

Snapshot logical ID: `providers.frozen_observation_compare`. No live HTTP.

## ES / news stack gates (FTEP-V1-001)

| Layer | Disposition | Notes |
| --- | --- | --- |
| Canonical news foundation (fixtures/replay) | **PASS** | `NewsArticleEvent` + deterministic tests |
| Aggregator → canonical bridge | **PASS** | `news/aggregator_bridge.py` (fixture-first) |
| Recorded eval → forward bridge | **PASS** | `RECORDED_ARTIFACTS_ONLY`; FTEP-ACT-06 auto-bridge still deferred |
| Observational live news ingress | **FAIL** | ACT-04 deferred; no end-to-end live ingress |
| Equity-ticker news for ES lane | **FAIL** | No CME ES headline feed; linkage policy needs owner decision |
| Moomoo ES futures context | **BLOCKED** | Stale evidence: `US_FUTURES_QUOTE` not entitled; needs local probe |
| Finviz live news | **FAIL** | `live_session` UNCONFIGURED in Wave A |
| FTEP manifest / preflight | **BLOCKED** | `PENDING_OWNER_DECISIONS` |
| G-A6/G-A7 campaign binding | **BLOCKED** | Matrix exists; owner manifest bindings + probes outstanding |
| Simulator calibration numeric gates | **BLOCKED** | Thresholds UNSET per calibration contract |

## Safe vs prohibited claims

| Safe (with cited evidence) | Prohibited |
| --- | --- |
| Bridge CG-01/CG-02 fixes and fixture tests pass | Qualifying **ACTUAL_FORWARD** evidence has started |
| Recorded-artifacts-only intelligence path is wired | Manifest is **FROZEN_FOR_ACTIVATION** without OD-11 |
| Capability matrix snapshot validates against schema | Any provider is **PROMOTED** without verification evidence rows |
| Gap engine returns deterministic disposition for FTEP-V1-001 | Live observational news is production-ready for campaign |
| Frozen snapshot compare runs on fixtures | Moomoo ES futures quotes are entitled without fresh probe |
| Preflight returns structured NOT_READY reasons | Execution-bearing calibration thresholds are set |

## UX hooks

Unified provider capability matrix HTTP projection and cross-surface enum normalization remain **deferred** (`DEFER-UNIFIED-UI-MATRIX`). Operator readiness CLI and projections are the supported path until a canonical matrix DTO exists.

## PIT research export (PIT-A-001)

Unified offline export binding (ADR-PIT-001 + ADR-RDATA-001):

| Module | Role |
| --- | --- |
| `research/pit_export.py` | Immutable export manifest: `source_sha256`, `prediction_cutoff_ns`, dataset fingerprints, experiment binding |
| `tests/research/test_pit_export.py` | Determinism and fail-closed validation |

Operator probe steps (no Live activation): [OPERATOR_PROBE_RUNBOOK.md](./OPERATOR_PROBE_RUNBOOK.md).

## Related artifacts

- Parent synthesis: `artifacts/wave-a-findings/reconciliation-gate.json`
- Wave B executive summary: `artifacts/wave-b-closure-report.json`
- ES/news smallest stack (goal §11 A–D): `artifacts/ftep-v1-001/es-news-provider-stack-selection.json`
- Notion sync payload: `artifacts/wave-b-notion-sync-payload.md`

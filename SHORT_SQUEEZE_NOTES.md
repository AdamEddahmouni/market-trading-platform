# Short Squeeze Research Screener notes

## Purpose and guarantees

`short-squeeze-project/short-squeeze-core` (v0.16.0) is a read-only research
screener, not an execution product. It compares named methodologies against
timestamped provider evidence, records provenance/freshness/status/missingness,
and refuses to turn missing evidence into zero or a synthetic fact. It states no
predictive validation, trade recommendation, broker access, or order placement.

## Architecture and modes

The Python package lives in `src/squeeze_core/`: acquisition, adapters,
analysis, contracts, evaluation, evidence, metrics, readiness, replay, research,
serialization, and validation. `apps/research_screener` serves the application;
the stable integration API is v1.0.0 with schema `batch14.integration.v1`.

| Mode | Providers/bind | Use |
|---|---|---|
| `FROZEN_DEMO` | bundled sanitized 13-candidate data; localhost | deterministic evaluation |
| `CLOUD_PROVIDER_MODE` | cloud-safe configured providers; `0.0.0.0:$PORT` | container/Railway |
| `LOCAL_FULL` | explicit private provider file and optional IBKR; localhost | workstation |

Configured adapters include Finviz Elite, NewsAPI, Finnhub, SEC EDGAR, and
local/remote IBKR. Configuration precedence is CLI, environment, explicit config,
private local provider file (LOCAL_FULL only), then safe defaults.

## Methodologies and evidence rules

Documented views are Legacy, peer-reference, Evidence-Gated Prime, and canonical
Phase 3A. Their outputs remain independent; a missing field is `UNKNOWN`, not
zero. Evidence-Gated Prime has the stable machine ID
`adam_evidence_gated_prime.v1`; the documented supported-weight floor is 65%.
The repository’s many ADRs formalize key research controls: separate rule
outcomes, no composite score in Phase 3A, no fabricated historical evidence,
outcome artifacts separate from acquisition, provenance for unknown bars, and
descriptive-only historical statistics. These controls are as important as the
screening indicators because they prevent post-outcome threshold tuning.

## Interfaces, tooling, and operations

- UI defaults to local port 8787; `/health`, `/ready`, and
  `/api/v1/integration/manifest` are documented endpoints.
- `tools/integration_acceptance.py` checks frozen integration; pytest uses
  synthetic fakes and should not call live providers.
- `tools/run_calibration_experiment.py` runs Phase 3D counterfactual policy
  experiments; `tools/run_calibration_suite.py` runs the full outcome-then-detection
  suite (see `docs/calibration/PHASE_3D_CALIBRATION.md`).
- Docker/Compose and Railway support use port 8080 in a container (host 8787).
- `tools/build_handoff_release.py` and `release_audit.py` create/audit an
  allowlisted, privacy-audited release. Provider auth and IBKR historical-export
  tools live under `tools/`.
- Optional security controls are `CSRF_PROTECTION` and `LOCK_SENSITIVE_API`, both
  default off. Credentials are environment values and frozen mode needs none.

## Important limits

This is a research evidence system, not a short-squeeze predictor. Provider
availability, freshness, mapping conflicts, historical source gaps, and field
admissibility govern results. Versioned docs under `docs/`, provider docs, API
contract, methodology docs, reproducibility guide, tests, and ADRs are the
authoritative detailed record; generated `dist/`, test-run folders and caches
are duplicated release/verification artifacts rather than separate products.

## Windows baseline (2026-08-14)

| Check | Result |
|---|---|
| `FROZEN_DEMO` server `:8787` | Pass — `/health` returns `mode: FROZEN_DEMO` |
| `integration_acceptance.py --mode frozen` | Pass (11/11 checks) |
| Full `pytest` | Partial — collection fails on missing `scripts/acquisition/acquire_biya_history` (pre-existing); some compatibility-hash and HuggingFace DNS teardown errors on this machine |
| SEC EDGAR live (`CLOUD_PROVIDER_MODE` + `.env`) | Pass — `doctor` reports `SEC_EDGAR: CONFIGURED`; `EdgardClient.recent_filings("NVDA")` returns filings |

## Windows baseline (2026-08-15)

| Check | Result |
|---|---|
| `pip install -e ".[test]"` in venv | Required before running server or pytest (`squeeze_core` not on path otherwise) |
| `integration_acceptance.py --mode frozen` | Pass (11/11 checks) after editable install |
| `tests/validation/test_outcome_acquisition_cli.py` | Pass (9/9) after `pythonpath = ["."]` in `pyproject.toml` |
| `FROZEN_DEMO` server | Pass — start with `SQUEEZE_APP_MODE=FROZEN_DEMO` and `python -m apps.research_screener --no-browser` |

**SEC setup walkthrough (free, no API key):**

1. In `short-squeeze-core/.env`, set `SEC_ENABLED=true` and a descriptive `SEC_USER_AGENT` (format: `AppName/1.0 (Your Name; project) your@email.invalid`). SEC requires a contact address in the User-Agent string.
2. Disable paid providers until keys exist: `FINVIZ_ENABLED=false`, `NEWSAPI_ENABLED=false`, `FINNHUB_ENABLED=false`, `IBKR_ENABLED=false`.
3. For live SEC filings (not frozen demo), run with `SQUEEZE_APP_MODE=CLOUD_PROVIDER_MODE` and verify: `python -m apps.research_screener.config doctor --mode CLOUD_PROVIDER_MODE --config .env`.
4. Keep `SQUEEZE_APP_MODE=FROZEN_DEMO` for zero-cost UI work; switch to `CLOUD_PROVIDER_MODE` only when testing live providers.

## Windows baseline (2026-08-16)

| Check | Result |
|---|---|
| CI focused pytest subset (5 modules, 80 tests) | Pass — includes cloud IBKR-unavailable + `demo_ready` readiness |
| `integration_acceptance.py --mode frozen` | Pass (11/11 checks) |
| `demo_ready` readiness | Fixed — no longer hardcodes 13 cases when canonical freeze has more rows |
| Full `pytest` suite | May fail `tests/compatibility/*` isolation guards when provider files drift; **CI subset is the release gate** — do not weaken compatibility guards |
| `acquire_biya_history.py` | Restored — full collection no longer blocked on missing script |

## Phase 3E Stage 2 pipeline (2026-08-17)

| Check | Result |
|---|---|
| `scripts/acquisition/run_stage2_pipeline.py` | Pass — freeze → outcomes → leakage → 3B → 3C |
| `tests/acquisition_phase3e/` | Pass — offline synthetic + live intake smoke |
| Fixture regen (15 IBKR symbols) | Pass — `generate_ibkr_cohort_phase_3a_fixtures.py` + 3B/3C anchors |
| `tools/run_calibration_suite.py` | Pass — reports under `reports/calibration/` |

**Phase 3E commands:**

```powershell
cd short-squeeze-project\short-squeeze-core
python scripts/acquisition/build_evidence_bundles.py
python -m squeeze_core.acquisition.phase3a_freeze.cli generate-phase3a-freeze
python scripts/acquisition/run_stage2_pipeline.py --skip-freeze
python scripts/generate_ibkr_cohort_phase_3a_fixtures.py
python scripts/generate_phase_3b_anchors.py
python scripts/generate_phase_3c_anchors.py
```

Use `--offline` with synthetic Batch 05 fixtures when live IBKR intake is unavailable.

## Phase 3F cohort expansion Batch 01 (2026-08-17)

| Check | Result |
|---|---|
| `docs/phase-3f-cohort-expansion-batch-01.md` | Preregistered before bar collection |
| IBKR detection-context + forward bars | Pass — 20/20 symbols (15 prior + CELZ, GDC, ADVB, GOAI, NXXT) |
| `scripts/acquisition/run_stage2_pipeline.py --force` | Pass — 20/20 leakage audits |
| Registry / calibration historical cohort | **22** case boundaries (`detection_predicate_candidates_historical.md`) |
| `tests/acquisition_phase3e/test_frozen_cohort_consistency.py` | Pass — cohort constants aligned across modules |

**Phase 3F Batch 01 symbols:** CELZ, GDC, ADVB, GOAI, NXXT (archived news co-occurrence from `biya_news.jsonl`; no scanner snapshot field values).

**Phase 3F commands:**

```powershell
cd short-squeeze-project\short-squeeze-core
python -m tools.ibkr_historical_export run
python scripts/acquisition/build_evidence_bundles.py
python -m squeeze_core.acquisition.phase3a_freeze.cli generate-phase3a-freeze
python scripts/acquisition/collect_forward_outcome_bars.py
python scripts/acquisition/run_stage2_pipeline.py --force
python scripts/generate_ibkr_cohort_phase_3a_fixtures.py
python scripts/generate_phase_3b_anchors.py
python scripts/generate_phase_3c_anchors.py
python tools/run_calibration_suite.py
```

## Phase 3F cohort expansion Batch 02 (2026-08-17)

| Check | Result |
|---|---|
| `docs/phase-3f-cohort-expansion-batch-02.md` | Preregistered before bar collection |
| IBKR detection-context + forward bars | Pass — 25/25 symbols (20 prior + VMAR, ATAI, CADL, CGEM, IOVA) |
| `scripts/acquisition/run_stage2_pipeline.py --force` | Pass — 25/25 leakage audits |
| Registry / calibration historical cohort | **27** case boundaries (`detection_predicate_candidates_historical.md`) |
| `tests/acquisition_phase3e/test_frozen_cohort_consistency.py` | Pass — cohort constants aligned across modules |

**Phase 3F Batch 02 symbols:** VMAR (news co-occurrence), ATAI, CADL, CGEM, IOVA (archived `prime_log.csv`; no scanner snapshot field values).

## Phase 3F cohort expansion Batch 03 (2026-08-17)

| Check | Result |
|---|---|
| `docs/phase-3f-cohort-expansion-batch-03.md` | Preregistered before bar collection |
| IBKR detection-context + forward bars | Pass — 28/28 symbols (25 prior + PMAX, STAK, APVO) |
| `scripts/acquisition/run_stage2_pipeline.py --force` | Pass — 28/28 leakage audits |
| Registry / calibration historical cohort | **30** case boundaries (`detection_predicate_candidates_historical.md`) |
| `tests/acquisition_phase3e/test_frozen_cohort_consistency.py` | Pass — cohort constants aligned across modules |

**Phase 3F Batch 03 symbols:** PMAX, STAK (archived `prime_log.csv`), APVO (archived screening-universe history; no scanner snapshot field values).

**n=30 threshold:** met — calibration may proceed to policy recommendation review.

## Phase 3D policy recommendation review (2026-08-17)

| Check | Result |
|---|---|
| `tools/run_calibration_suite.py` | Pass — 4 reports regenerated at n=30 |
| `docs/calibration/PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md` | Complete — formal review record |
| ADR-0067 (detection policy) | Revised at n=30 — retain baseline, reject all variants |
| ADR-0068 (outcome policy) | Created — retain ±25%/24h, reject threshold raises |
| `tests/calibration/test_detection_ablation.py` | Pass — baseline case_count=30, momentum_full flip set locked |

**Recommendations:** retain `phase_3b_research_detection_policy.v1` and `phase_3b_outcome_label_policy.v1` unchanged. Adam methodology calibration complete (ADR 0069 + 0070).

## IMP historical squeeze context (2026-08-17)

| Check | Result |
|---|---|
| `donor_bridge/data/historical_squeeze_cohort_v1.json` | 30 case boundaries from Phase 3B research dataset |
| `donor_bridge/historical_cohort.py` | Per-symbol `historical_context` on workspace squeeze payloads |
| RESEARCH `squeeze_historical_cohort` panel | Cohort outcome/classification distribution chart |
| `tests/donor_bridge/test_historical_squeeze_cohort.py` | Pass — AVTX in cohort, BIYA×2, donor-down still has context |

## IMP squeeze institutional evidence cards (2026-08-17)

| Check | Result |
|---|---|
| `donor_bridge/institutional_ignition.py` | Options ignition card from `ADMITTED-OPTIONS-BIYA-001` when replay entitled |
| BIYA workspace squeeze (donor unavailable) | Pass — supplemental ignition cards with ADMITTED Options |
| AVTX workspace squeeze (donor available) | Options card honest UNAVAILABLE (no BIYA fixture entitlement) |
| `tests/donor_bridge/test_institutional_ignition.py` | Pass — institutional cross-ref at replay cutoff |

## IMP live-provider squeeze bridge (2026-08-17)

| Check | Result |
|---|---|
| `squeeze_client.py` | `fetch_current_candidates`, `fetch_current_candidate_detail`, `fetch_donor_deployment_mode` |
| `build_explore_squeeze_scanner_payload` | EXPLORE live scanner table with detection summary |
| `build_workspace_squeeze_payload(data_mode=current)` | Workspace detail from `/api/current/candidate/{symbol}` |
| `GET /explore/squeeze/scanner` | IMP API route for scanner explore |
| `tests/donor_bridge/test_live_squeeze_bridge.py` | Pass — mocked current projections |

## Phase 3F cohort expansion Batch 04 (2026-08-17)

| Check | Result |
|---|---|
| `docs/phase-3f-cohort-expansion-batch-04.md` | Preregistered — BIYA IBKR frozen-boundary alignment |
| Yahoo-chart bar import | Pass — 620 detection-context + 364 forward-outcome bars |
| `scripts/acquisition/import_biya_yahoo_bars_to_ibkr_intake.py` | New intake converter |
| IBKR cohort symbols | **29** (28 prior + BIYA) |
| Stage 2 leakage audit | Pass — 29/29 |
| Evidence bundles | Pass — 29/29 |
| Phase 3A freeze result for BIYA | **Complete** — batch-05 manifest registration + 29/29 freeze |

**Note:** Phase 2V BIYA evaluation boundaries (`BIYA_EARLIEST` / `BIYA_LATEST`) remain unchanged per ADR-0054. Batch 04 adds BIYA to the IBKR frozen-boundary acquisition track only.

## IMP institutional borrow + depth cards (2026-08-17)

| Check | Result |
|---|---|
| `build_institutional_borrow_card` | PARTIAL for BIYA — SEC disclosure cross-ref |
| `build_institutional_depth_card` | ADMITTED for NVDA at replay cutoff |
| `merge_institutional_ignition_cards` | Borrow, Options, Depth merged on workspace payloads |
| `tests/donor_bridge/test_institutional_ignition.py` | Pass |

## IMP scanner NOW attention (2026-08-17)

| Check | Result |
|---|---|
| `build_squeeze_scanner_attention_items` | Up to 3 ephemeral scanner rows on NOW feed |
| `projection_scanner_fail_closed` | Pass — scanner explore fail-closed when donor down |
| `imp_scanner_explore_http` | IMP `/explore/squeeze/scanner` acceptance check |
| `imp_explain_squeeze_scanner` | Explain resolves `explain:squeeze:scanner:{symbol}` when rows exist |

## Lane acceptance evidence (2026-08-17)

| Check | Result |
|---|---|
| `evidence/integration/squeeze-lane-acceptance.json` | Regenerated — `status: PASS` (`donor_mode: CLOUD_PROVIDER_MODE`, `scanner_row_count: 3`) |
| Scanner + attention checks | Pass — `projection_scanner_rows`, `imp_scanner_explore_rows`, `imp_workspace_scanner_http`, `imp_explain_squeeze_scanner` |
| `--require-scanner-rows` | Pass — live scanner populated (AVTX, GME, BIYA via `CLOUD_BOOTSTRAP_SYMBOLS` + SEC) |
| `CLOUD_BOOTSTRAP_SYMBOLS` | Optional dev seed when Finviz/IBKR discovery is empty |
| `tools/run_donor_demos.ps1 -Start squeeze-cloud` | Starts `start_cloud.py` with live scanner defaults |

## Adam scoring calibration (2026-08-17)

| Check | Result |
|---|---|
| `tools/run_adam_calibration.py` | Weight-floor sweep 50–70% on live evidence profiles |
| Recommendation | **RETAIN** `MIN_DIMENSION_WEIGHT = 65%` |
| `weights_validated` metadata | `true` at default floor |
| ADR | [0069](../short-squeeze-project/short-squeeze-core/docs/adr/0069-adam-evidence-gated-prime-calibration-findings.md) |

## Adam classification threshold calibration (2026-08-17)

| Check | Result |
|---|---|
| `tools/run_adam_threshold_calibration.py` | PRIME/SUBPRIME/WATCH + coverage gate sweep on live profiles |
| Recommendation | **RETAIN** baseline gates (70/70 PRIME, 85% HIGH coverage) |
| `thresholds_optimal` metadata | `true` at default thresholds |
| ADR | [0070](../short-squeeze-project/short-squeeze-core/docs/adr/0070-adam-classification-threshold-calibration-findings.md) |

## Live scanner soak (2026-08-17)

| Check | Result |
|---|---|
| `tools/integration/squeeze_cloud_soak.py` | 3-iteration soak with refresh — `status: PASS` |
| Stable row counts | Donor + IMP scanner both held 3 rows across polls |
| Lane acceptance | `evidence/integration/squeeze-lane-acceptance.json` — `PASS`, `scanner_row_count: 3` |
| Limitation | SEC-only cloud session — rows stay `UNEVALUABLE`/`STALE` without Finviz/IBKR keys |

## Live scanner local providers (2026-08-17)

| Check | Result |
|---|---|
| `start_cloud.py --load-local-providers` | Preloads `.private/providers.env` for local cloud soak |
| `tools/run_donor_demos.ps1 -Start squeeze-cloud-providers` | Donor launcher with provider preload |
| `tests/app/test_start_cloud_local_providers.py` | Pass |

Restart the donor with `squeeze-cloud-providers` (not plain `squeeze-cloud`) to exercise
Finviz-backed Adam scoring; use soak `--require-evaluable` to gate evaluable rows.

## Finviz per-symbol bootstrap enrichment (2026-08-17)

| Change | Detail |
|---|---|
| `live_providers.refresh_all` | Calls `ensure_symbols` even when bulk screener fails or omits manual symbols |
| `short_pressure_fields` | On-demand per-symbol Finviz export when screener cache misses |
| Bootstrap | `CLOUD_BOOTSTRAP_SYMBOLS` trigger explicit Finviz export before warm cycles |
| Frozen/detail enrichment | `ensure_symbols` before `get_row` in snapshot helpers |
| Tests | `tests/app/test_finviz_bootstrap_enrichment.py` |

Rerun evaluable soak after restarting donor with `squeeze-cloud-providers` during market hours:

```powershell
python tools/integration/squeeze_cloud_soak.py --trigger-refresh --require-evaluable
```

**2026-08-17 verification:** Evaluable soak **PASS** — 7 donor rows, 7 evaluable Adam
classifications (all WATCH), IMP scanner 7/7 stable across 3 iterations. Artifact:
`integrated-market-platform/evidence/integration/squeeze-cloud-soak.json`. Finviz
auto-refresh is wired at startup (`ensure_finviz_operational`), on each provider refresh
cycle (`maybe_recover_finviz` on 401), and in `run_donor_demos.ps1` /
`run_supervised.ps1 -CloudProviders` preflight.

## External cohort preregistration (2026-08-17)

| Doc | `docs/phase-3f-external-discovery-preregistration.md` |
| Batch 05 lane | Fresh Finviz Elite export — [phase-3f-cohort-expansion-batch-05-external.md](../short-squeeze-project/short-squeeze-core/docs/phase-3f-cohort-expansion-batch-05-external.md) |
| Normalized artifact | `intake/batches/phase-3f-cohort-expansion-05-external/normalized/batch3f05_external_discovery_rows.json` |
| Status | **Captured (2026-08-17)** — symbols AACB, AACG, AACI, AACP, AADX; identity audit PASS; IBKR bars collected |

## Batch 07 readiness audit (2026-08-17)

| Check | Result |
|---|---|
| `tools/run_batch07_readiness.py` | 29-case operation-readiness report from `ibkr-batch-05` |
| BIYA included | Yes — final symbol in frozen cohort |
| PRICE_RANGE Batch 07 | `BLOCKED_MISSING_SEMANTICS` (expected price-level blocking) |
| Doc | [batch-07-readiness-audit.md](../short-squeeze-project/short-squeeze-core/docs/batch-07-readiness-audit.md) |

## SS P2 catalyst/attention runtime + IBKR lending (2026-08-19)

| Check | Result |
|---|---|
| `donor_bridge/market_context_adapter.py` | BOXL fixture catalyst → cross_lane + SS P2 structs |
| `donor_bridge/lending_adapter.py` | IBKR borrow → `SecuritiesLendingSnapshot` + cross_lane lending fields |
| `session_state.py` | Emits `securities_lending_snapshot` on current rows when IBKR borrow present |
| `evaluator.py` | Catalyst strength, thesis invalidation, lending constraint_pressure |
| UI `CatalystAttentionBlock` | Workspace panel shows catalyst/attention/lending (honest UNAVAILABLE) |
| `tools/research/squeeze_cross_lane_experiments.py` | JQ-2/3/5 lift harness → `reports/research/squeeze_cross_lane/` |
| Research report | `cross_lane_lift_report.json` — 24 cases, catalyst lift +1.0 on fixture harness |
| Tests | `test_market_context_adapter`, `test_lending_snapshot`, extended causal evaluator (31 total pass) |

**Commands:**

```powershell
cd integrated-market-platform
python -m unittest tests.donor_bridge.test_market_context_adapter tests.donor_bridge.test_lending_snapshot tests.donor_bridge.test_causal_squeeze_projection
python tools/research/squeeze_cross_lane_experiments.py

cd short-squeeze-project\short-squeeze-core
python -m unittest tests.intelligence.test_causal_evaluator
```

Evaluable cloud soak (market hours + Finviz): `python tools/integration/squeeze_cloud_soak.py --trigger-refresh --require-evaluable`


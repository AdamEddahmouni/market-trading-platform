# FTEP-V1-002 — Section 32 final executive report

Generated: 2026-09-12 (orchestrator close)

# Executive result

**SIGNAL_ONLY_AUTHORIZED_MARKET_CLOSED**

Owner explicitly authorized Phase 1 **SIGNAL_ONLY** only (receipt: `signal-only-authorization-receipt-2026-09-12.json`). No empirical session started: US equity RTH closed (Saturday 2026-09-12). Engineering stop line preserved: zero decision locks, orders, Live activation, or paid provider purchases; **post-freeze manifest mutations: 0**.

# Repository integration

| Item | Value |
| --- | --- |
| Starting SHA | `099388f7f23e31e3d01107ceeba9c8822903848c` |
| Final SHA | `a754f5e` _(full: run `git rev-parse HEAD` on branch)_ |
| Base | `work/ftep-v1-002-us-equity-news` @ `099388f` (same as `work/ftep-v1-activation`) |
| PR #22–#29 | #22 green; #23 green; #24–#28 show intermittent `validate-docs` / `validate-python-changed` on stack bases; **#29** (`work/ftep-v1-002-us-equity-news`) had `validate-docs` fail on broken WORK_LOG link — fixed @ `ddded1b` — **not merged** (owner merge auth only) |
| V1-002 PR | Created/updated from `work/ftep-v1-002-us-equity-news` after commit push |
| Merges performed | **0** |
| Worktree | Primary repo `C:/Users/adame/Desktop/market-trading-platform`; branch `work/ftep-v1-002-us-equity-news` |
| Tree state | Intentional FTEP-V1-002 delta staged; local perf artifact drift (`g8-runtime-performance.json`, `p3-plan-cli-check.json`) excluded from commits |

# Backup

| Item | Value |
| --- | --- |
| Stash | `stash@{0}` — `ftep-v1-002-orchestrator-backup-2026-09-12` |
| Backup ref | `refs/backup/ftep-v1-002-dirty-2026-09-12` → `f6395938fca4ab9692b912dec64d0748d475136b` |

# FTEP-V1-001

| Item | Value |
| --- | --- |
| Slug | `FTEP-V1-001` |
| Campaign ID | `FTCAMP-69c36ba23813c009c27ee83924834d46f5804d0a0fa037e37adb133f8bfea99c` |
| Fingerprint | `69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C` |
| Unchanged? | **Yes** — no diff under `artifacts/forward-test-campaigns/FTEP-V1-001/` |
| Current blocker | `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT` (ES `US_FUTURES_QUOTE` / CME Quote Store) |

# FTEP-V1-002 frozen identity

| Item | Value |
| --- | --- |
| Slug | `FTEP-V1-002` |
| Campaign ID | `FTCAMP-f7083180990bc59578ca045e1e1318a356421bbc9b81ee514c14130cb0b356b1` |
| Fingerprint | `F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1` |
| Freeze timestamp | `2026-09-12T16:30:00Z` (owner-signed `2026-09-12T16:30:00Z`) |
| Paper account | `7CBA5536EED17C4A6246327EE7ABF223C58627660B93A642D8A99C2AEC10A579` (canonical Internal simulation Paper) |
| Activation status | `FROZEN` |

# Final owner configuration

- **AAPL** — campaign universe
- **MSFT** — campaign universe
- **NVDA** — campaign universe
- **AMZN** — campaign universe
- **META** — campaign universe
- **SPY** — `benchmark_symbols` / `BENCHMARK_CONTEXT_ONLY` only (not campaign target symbol)
- **SIGNAL_ONLY** Phase 1 — `binding.test_mode`
- **Internal simulation Paper** — bound (same ID as V1-001 canonical ledger)
- **Freeze** — approved under OD-11 (`BIND_FREEZE_PREFLIGHT_ONLY`)
- **First empirical session** — **Owner authorized** via external receipt; frozen manifest `operator_attestation.signal_only_session_authorized` remains `false` (immutable post-freeze)

# Methodology

| Topic | Binding |
| --- | --- |
| Hypothesis | News-catalyst cohort comparison (preregistered FTEP-V1 protocol) |
| Baseline arm | `news_deterministic_baseline@1.0.0` |
| AI arm | `news_ai_enhanced@1.0.0` |
| Catalyst taxonomy | `CATALYST_TAXONOMY_CONTRACT_V1` / registry `news/catalysts/1.0.0` |
| Cadence | `EVENT_DRIVEN` |
| RTH | `US_EQUITY_RTH` / calendar scope |
| Horizons | Primary binding `evaluation_horizon_ns`: 300000000000 (5m) |
| Primary metric | Per protocol §8 (`percentage_return` / paired bootstrap CI at V1-001 freeze parity) |
| Sample floors | Inherited FTEP core duration floors when execution phase authorized |
| Cohort key | `(symbol, decision_bucket, evaluation_horizon_ns)` |
| Benchmark diagnostics | SPY context-only benchmark symbols in manifest |

# Provider status

### Finviz Elite

| Field | Status |
| --- | --- |
| Config | `LOCAL_PROBE_REQUIRED` — no API key in operator session |
| Connectivity | Not probed live this session |
| Entitlement | Owner Elite ($0 incremental) — stale verified export |
| Capability | `NEWS_EXPORT` — matrix satisfied via stale evidence |
| Freshness | Authoritative stale: `evidence/market_data/finviz/capability-report.json` (`2026-08-22`) |
| Campaign suitability | CONTEXT_ONLY; SIGNAL_ONLY + `RECORDED_ARTIFACTS_ONLY` defers live ingress (`WAVE-A-002`) |
| Receipt | `artifacts/ftep-v1-002/finviz-local-probe-status-2026-09-12.json` |

### Moomoo

| Field | Status |
| --- | --- |
| Connectivity | OpenD reachable; quote context PASS |
| Entitlement | `US_EQUITY_L1` entitled + receiving |
| Equity L1 | `SAMPLE_VERIFIED` |
| Target symbols | AAPL, MSFT, NVDA, AMZN, META (+ SPY benchmark context) |
| SPY | Benchmark context only |
| Realtime/delayed | Realtime L1 where entitled |
| Campaign suitability | `US_EQUITY_PROSPECTIVE_MARKET_EVIDENCE`: `SAMPLE_VERIFIED` |
| Receipt | `artifacts/ftep-v1-activation/provider-probe-moomoo-summary-2026-09-12.json` |

### SEC

Optional `PUBLIC_FILINGS` context; not required for Phase 1 SIGNAL_ONLY baseline.

### IBKR

Unavailable as $0 immediate US equity L1 path (~$500 funding constraint); documented observational/delayed only.

# Campaign-bound evidence

- **G-A6**: Satisfied for `FTEP-V1-002` via frozen-manifest overlay → `MOOMOO` / `US_EQUITY_L1` at `CAMPAIGN_BOUND` with manifest fingerprint evidence.
- **Market-data authority**: `market_data_bindings.authority` → MOOMOO `US_EQUITY_L1`.
- **Binding receipt**: `artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json` + `artifacts/ftep-v1-002/frozen-manifest-verification-ftep-v1-002-2026-09-12.json`.

# Preflight

**Disposition:** `READY` (PAPER / FORWARD_TEST, persistence enabled, frozen manifest, zero-cost safety constraints).

# Campaign readiness

| Gate | Disposition |
| --- | --- |
| Manifest | `FROZEN` |
| Preflight | `READY` |
| SIGNAL_ONLY | Engineering-ready; **session not started** |
| EXECUTION | Not authorized |
| Live | Forbidden |

Overall campaign readiness: **READY**.

# Validation

| Command | Result |
| --- | --- |
| `unittest` FTEP-V1-002 + finviz + coverage | **16/16 OK** |
| `python tools/imp.py validate fast` | **21 passed**, 0 failures |
| `python tools/imp.py validate changed` | **2159 passed**, 37 skipped, 0 failures (~90s) |
| V1-001 frozen verifier | `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT` (expected) |
| V1-002 frozen verifier | `VERIFIED_FROZEN_READY_FOR_PREFLIGHT` |

# Docs / Notion

- Updated engineering docs: `FTEP_CAMPAIGN_CATALOG.md`, `US_EQUITY_PROFILE_V1.md`, `CATALYST_TAXONOMY_CONTRACT_V1.md`, provider/news docs, `WORK_LOG.md`, `PROGRAM_STATUS.md`.
- Notion: payload at `artifacts/ftep-v1-002/notion-sync-payload-2026-09-12.md` (no live Notion MCP write in repo).

# Parallel extra work

Opportunity Engine / PIT export track remains on open PR #27 — not merged; no conflict with V1-002 stop line.

# Safety

| Counter | Count |
| --- | --- |
| Empirical SIGNAL_ONLY sessions started | **0** |
| Decision locks | **0** |
| Orders / execution segments | **0** |
| Live activations | **0** |
| Paid provider activations | **0** |
| Incremental cost USD | **$0** |

# Remaining blocker

Merge canonical FTEP infrastructure PR stack **#22–#28** into integration base before production-line activation UI wiring (not required to authorize first governed SIGNAL_ONLY session once owner explicitly requests it).

# Section 37 orchestrator handoff (2026-09-12 activation pass)

| Field | Value |
| --- | --- |
| **Classification** | `SIGNAL_ONLY_AUTHORIZED_MARKET_CLOSED` |
| **Campaign** | `FTEP-V1-002` / US-equity-news-catalyst |
| **Campaign ID** | `FTCAMP-f7083180990bc59578ca045e1e1318a356421bbc9b81ee514c14130cb0b356b1` |
| **Fingerprint** | `F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1` |
| **Git** | `work/ftep-v1-002-us-equity-news` @ `4f6f05e` (pushed) |
| **Authorization** | `artifacts/ftep-v1-002/signal-only-authorization-receipt-2026-09-12.json` |
| **Machine readiness** | `artifacts/ftep-v1-002/machine-readiness-receipt-2026-09-12.json` |
| **Launch prep** | `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md` |
| **FTEP-V1-001** | Unchanged; `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT` |
| **Sessions started** | **0** |
| **Safety** | Paper orders=0, Live orders=0, paid activations=0, manifest mutations=0 |

**NEXT ACTION:** On next **US_EQUITY_RTH** open window, set `IMP_PERSIST_STATE=1`, confirm `campaign-readiness FTEP-V1-002` → `READY`, then start first governed SIGNAL_ONLY session per launch prep (no execution segment).

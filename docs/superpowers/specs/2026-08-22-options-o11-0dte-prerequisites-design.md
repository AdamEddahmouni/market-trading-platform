# Options O11 — 0DTE Specialization Prerequisites Design

**Date:** 2026-08-22
**Status:** Prerequisite infrastructure scaffold — no Phase C dataset admitted, no research claims
**Scope:** Workstream I authorized increment only (fixture-first prerequisite infrastructure)
**Research plan:** [`docs/research/OPTIONS_RESEARCH_PLAN.md`](../../research/OPTIONS_RESEARCH_PLAN.md) §2.2–2.3, §10
**Gap analysis:** [`docs/research/OPTIONS_CAPABILITY_GAP_ANALYSIS.md`](../../research/OPTIONS_CAPABILITY_GAP_ANALYSIS.md) §5 ("0DTE intraday surface → research-only until O11 + execution correctness")
**Audit baseline:** [`docs/research/OPTIONS_CURRENT_STATE_AUDIT.md`](../../research/OPTIONS_CURRENT_STATE_AUDIT.md) §2 ("0DTE specialization: None")

---

## 1. What O11 full completion requires (and does NOT have yet)

O11 (0DTE intraday surface / execution) is complete only when **all three** layers exist and are
evidenced end-to-end:

| Layer | Requirement | Status today |
|---|---|---|
| **Data** | Phase C dataset `intraday chain snapshots` admitted per [`OPTIONS_RESEARCH_PLAN.md`](../../research/OPTIONS_RESEARCH_PLAN.md) §2.3, with aligned `event_time`/`available_time` bitemporality (§2.4 partitioning rules) | **PENDING — not procured, not admitted.** Admission is gated exactly like Phase B (`OPTIONS_PHASE_B_ADMISSION.md` checklist pattern). |
| **Analytics** | Expiration-aware analytics: intraday surface behavior on the expiry day, IV/GEX-class features with proxy labeling, walk-forward protocol stratified for the `0DTE-heavy` regime (§9) | **Not implemented in this increment — post-admission scope by design.** |
| **Execution** | Execution-correctness linkage: fills, spread/slippage/legging costs, fill probability under 0DTE gamma decay — the O9 dependency named in gap analysis §5 | **Not implemented in this increment; bar-only simulator today.** |

## 2. What THIS increment delivers

Fixture-proven **prerequisite infrastructure only**, in a new fail-closed package
[`src/market_platform_foundation/options/zerodte/`](../../../src/market_platform_foundation/options/zerodte/):

1. **`contracts.py`** — `IntradayChainSnapshotRecord`, a frozen dataclass for one underlying-level
   intraday chain snapshot:
   - Bitemporal pair `event_time_ns` + `available_time_ns` (integer epoch nanoseconds), mirroring
     the event-time/available-time discipline of `cboe_options` observations
     (`market_platform_foundation/cboe_options/contracts.py`) and research plan §2.4.
   - `expiration_timestamp_ns` plus derived `dte_hours`.
   - Deterministic `is_zero_dte` rule: the snapshot is 0DTE iff the expiration's
     **America/New_York calendar date equals the snapshot reference (event) time's ET calendar
     date**. Timezone handling: all date comparisons run in `America/New_York` via
     `zoneinfo`, because US equity option expirations settle against the **16:00 ET session
     close**; comparing UTC dates would misclassify evening-ET snapshots across the midnight UTC
     boundary. Anchoring to the ET session close means the "0DTE day" spans from the prior
   session close to 16:00 ET of expiry day — a snapshot stamped any time on expiry day in ET
   (including after-hours up to local midnight) still classifies as same-expiry-day, while the
   quality layer separately flags snapshots whose event time is past the 16:00 ET close
   (`EXPIRY_PAST_SESSION_CLOSE`). DST transitions are handled by `zoneinfo`; the rule uses
   wall-clock ET dates, never fixed offsets.
   - `strikes` as an immutable tuple; `multiplier` passthrough.
   - Provenance envelope fields following provider-metadata conventions already used by
     `cboe_options` contracts (`publisher`, `retrieved_time`, `ingested_time`, `content_hash`,
     `quality_flags`, `provenance_ref`, `lifecycle="OBSERVED"`, `predictive=False`) reusing the
     `cboe_options` vocabularies via import only (`PitHistoryClass`, `OptionsFeatureLayer`,
     `AvailabilityPrecision`, `CoverageScope`). No cboe file is edited.

2. **`quality.py`** — quality taxonomy + gates that **fail closed when fields are absent**:
   - Stale-snapshot detection with explicit available-time lag threshold parameters
     (`StalenessPolicy.max_available_lag_ns`).
   - Liquidity gates (`LiquidityPolicy`): bid AND ask presence, width cap (absolute and/or
     percent-of-mid); missing quote fields produce blocking flags, never silent passes or
     zero-fills (anti-pattern "missing flow → zero", research plan §4.3).
   - Expiration-boundary checks anchored to the 16:00 ET session close of the expiry's ET
     calendar date.
   - Duplicate-snapshot detection keyed on `(underlying, event_time_ns)`.

3. **`pit.py`** — admissibility join: a snapshot is usable at decision time `T` iff
   `available_time_ns <= T` **and** `event_time_ns <= T`. Lookahead cases (either timestamp in
   the future of `T`) are rejected with an explicit reason, mirroring platform PIT join policy
   (`runtime/pit_joins.py` semantics; research plan §2.4 "never allow newer Options observation
   into earlier decision").

4. **`admission.py`** — manifest-driven admission scaffold mirroring the Phase B shape
   (`logical_id`, `schema_version`, `status`, `admission_requirements`, `dataset_slots`,
   `notes`) and the fail-closed evaluation pattern of
   `options/research/harness.evaluate_phase_b_admission()`. The default manifest is an embedded
   constant with `status="PENDING"` and empty `dataset_slots`; external manifests may be passed
   explicitly. Default state fails closed:
   `admitted=False`, `blocking_reasons=["PHASE_C_MANIFEST_STATUS_PENDING",
   "PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_NOT_ADMITTED"]`.

5. **Fixture** [`tests/fixtures/options/o11_chain_snapshots.json`](../../../tests/fixtures/options/o11_chain_snapshots.json)
   — clearly labeled **synthetic contract fixtures** (`fixture_kind: SYNTHETIC_CONTRACT_FIXTURE`,
   explicit non-market-data disclaimer): healthy 0DTE snapshot, stale snapshot, expired-boundary
   snapshot, wide-quote snapshot, missing-quote snapshot, and a duplicate-event-time pair. These
   fixtures exercise code paths only; they prove nothing about real markets.

6. **Tests** [`tests/options/test_o11_zerodte_prerequisites.py`](../../../tests/options/test_o11_zerodte_prerequisites.py)
   — deterministic unittest module covering contract round-trip, the 0DTE boundary matrix
   including TZ edges (UTC-vs-ET midnight crossing, DST boundary), staleness thresholds,
   liquidity fail-closed behavior, PIT lookahead rejections, duplicate detection, and admission
   fail-closed default.

The suite directory `tests/options/` is covered by the validation manifest suite id `options`
(`test_globs: ["tests/options/test_*.py"]`, `source_globs` include
`src/market_platform_foundation/options/**`), so no manifest changes are needed (none permitted).

## 3. Evidence terminology (explicit)

| Term | Meaning | Applies here? |
|---|---|---|
| **Fixture-proven infrastructure** | Code paths demonstrated deterministic and fail-closed on synthetic labeled contracts inside this repo | **YES — this is the only claim this increment makes.** |
| **Forward validation** | Out-of-sample evidence on admitted, time-aligned real data (walk-forward, purge/embargo per §2.4) | **NO — impossible until Phase C datasets are procured and admitted.** |
| **Tradeable edge** | Positive net-of-cost EV after execution-correctness modeling, validated forward | **NO — and none may be claimed from this work.** |

Any document conflating fixture tests with forward validation or edge claims would violate the
evidence hierarchy of research plan §5 and is out of bounds.

## 4. Explicit boundaries of this increment

- **No analytics**: IV solver, GEX/dealer-gamma proxies, intraday surface fitting, P vs Q on
  0DTE — all post-admission scope (research plan §11: "0DTE intraday before O9 execution"
  stays un-researched). The package contains no Greek, IV, or exposure math.
- **No live capture**: no provider calls, no Moomoo/Tradier bytes, no network I/O.
- **No fabricated Greeks or dealer positioning**: record carries quotes/strikes/multiplier only.
- **No research-to-directive promotion**: everything stays `research_only=True`,
  `predictive=False`; no strategy, score, or signal output exists.
- **Fail closed everywhere**: absent timestamps, absent quotes, unknown provenance, pending
  admission — every unknown path returns a rejection reason, never a permissive default.

## 5. Phase C blockage statement and exact unblock action

**Blocked.** Phase C dataset `intraday chain snapshots` (research plan §2.3, requirement for
O11) has admission status **PENDING**; no procurement authorization, no payload, no fixture
manifest slots exist. Consequently O11 analytics and execution-correctness linkage cannot start
and remain blocked behind the same governance gate as Phase B.

**Exact unblock action** (mirrors the Phase B checklist in
[`OPTIONS_PHASE_B_ADMISSION.md`](../../engineering/OPTIONS_PHASE_B_ADMISSION.md)):

1. Obtain procurement authorization for a lawful source of full intraday option-chain snapshots
   (per-symbol chain with bid/ask, strikes, multiplier, exchange metadata) — ADR review required
   before any live-provider bytes are promoted.
2. Create `manifests/options/phase-c-intraday-chain-admission.json` with the shape mirrored by
   `options/zerodte/admission.DEFAULT_ADMISSION_MANIFEST`: `status` initially `PENDING`,
   requirement `PHASE_C_INTRADAY_CHAIN_SNAPSHOTS` (`NOT_ADMITTED`), `dataset_slots: []`.
3. Populate `dataset_slots` with `{requirement_id, admitted_fixture_id, content_path}` entries;
   each admitted payload gets a fixture admission manifest under `tests/fixtures/providers/options/`
   with aligned `event_time`/`available_time`.
4. Set manifest `status` to `ADMITTED` only after steps 1–3, then re-run
   `evaluate_phase_c_admission()` (must return `admitted=True` with zero blocking reasons) and
   the O11 harness smoke (`available=True`).
5. Only then authorize the post-admission increments: expiration-aware analytics and the
   execution-correctness linkage, each with its own design doc and forward-validation gates.

Until step 4 completes, every entry point in `options/zerodte/` reports blocked/PENDING and
fails closed.

## Related documents

- [`docs/research/OPTIONS_RESEARCH_PLAN.md`](../../research/OPTIONS_RESEARCH_PLAN.md)
- [`docs/engineering/OPTIONS_PHASE_B_ADMISSION.md`](../../engineering/OPTIONS_PHASE_B_ADMISSION.md)
- [`manifests/options/phase-b-chain-history-admission.json`](../../../manifests/options/phase-b-chain-history-admission.json)

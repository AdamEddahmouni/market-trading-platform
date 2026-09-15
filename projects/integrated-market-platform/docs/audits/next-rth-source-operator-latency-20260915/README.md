# Next-RTH source→operator latency audit

**Lane:** Isolated P6 (`diagnosis/observability-latency-20260915` from `origin/main`)
**Cutoff SHA:** `7aade60bf8041df5ebf9f0ac856d5d8802845c8d`
**Status:** diagnosis only — unmerged; does not edit frozen RTH, EventV1 schema, or other-lane files
**Not claimed:** `LIVE_HOT_PATH_LATENCY_VALIDATED`, `PROSPECTIVE_HOT_PATH_LATENCY_CAPTURED`

This audit classifies existing clocks for Tuesday next-RTH **source publication → operator action** latency. It prefers `EventV1`, BUILD 03 provenance, `NewsArticleEvent` clocks, `DetectionV1`, `OpportunityV1`, ranked-book rank metadata, UI API projections, and `ExecutionDecisionTraceV1`. It does **not** propose an OpenTelemetry platform or a new envelope.

File ownership respected: no edits to `opportunity_projections.py`, news normalize EventV1 mapper, Item 9 kline fetch, launcher, or Vite. Production schema changes owned by P1 are a **patch plan only**.

## Classification legend

| Label | Meaning |
|---|---|
| **AVAILABLE** | Field exists, semantics are explicit, and a production or governed software path can populate it |
| **DERIVABLE** | No dedicated hop stamp, but a correct delta can be computed from two existing clocks without schema change |
| **MISSING** | No field, payload key, or honest proxy on the next-RTH path |
| **AMBIGUOUS** | A timestamp exists but is the wrong clock kind, conflated with another hop, decision-time rather than processing-time, or not correlated |

Clock kinds (from [OBSERVABILITY_STANDARD.md](../../platform/OBSERVABILITY_STANDARD.md)): provider/source time, received time, available/eligibility time, processed time, wall vs process-monotonic. These must not be mixed in one delta without a label.

## Hop classification (next-RTH news/catalyst → operator)

| Hop | Class | Existing field(s) | Evidence |
|---|---|---|---|
| Source publication / event | **AVAILABLE** on news plane; **AMBIGUOUS** on `EventV1` | `NewsArticleEvent.published_time` + `published_time_quality`; `EventV1.event_time_ns` | News never assigns retrieval as publication (`classify_publication_time`). Quality `UNKNOWN` / date-only → not a usable source clock. `EventV1.event_time_ns` is economic/source event **or** Finviz discovery `available_time_ns` / `discovered_at`. **No news→EventV1 mapper on this SHA** (P1). |
| Provider retrieval | **AMBIGUOUS** | `NewsArticleEvent.retrieved_time`; aggregator `received_time`; `EventV1.provider_time_ns` | Pull clients stamp HTTP completion (`news/providers.py` `received_at`) onto every article. That is not a vendor “indexed at” clock. `EventV1.provider_time_ns` often copies `event_time_ns` (Finviz discovery). |
| IMP receive | **AVAILABLE** | `EventV1.received_time_ns`; `NormalizationContext.received_time_ns`; news `retrieved_time` | BUILD 03 adapters persist receive separately from event time. On pull news, receive ≈ HTTP completion (same instant as “provider retrieval”). |
| Normalization | **AMBIGUOUS** | `EventV1.available_time_ns`; `ProviderProvenance.availability`; hot-path `normalized_at` | Collector sets `normalized_at = available_time_ns`. `available_time_ns` is PIT eligibility (`derive_available_time_ns`), not adapter completion. LIVE_OBSERVED available often **equals** receive → hop reports 0. No `processed_at_ns` on `EventV1`. |
| Detector | **AMBIGUOUS** | `DetectionV1.detected_at_ns` | Populated as `snapshot.decision_time_ns`, not detector wall-clock. `NEWS_EVENT` exists, but news plane is not joined to `EventV1` here. Hot-path software-wired merge onto the first ingress row is explicitly **non-authoritative**. |
| Opportunity creation | **AMBIGUOUS** | `OpportunityV1.created_at_ns` | Set to `opportunity_decision_time_ns` (identity/PIT), not mint wall-clock. API may project `created_at_ns` from persist; metadata ingest timestamps are stripped. |
| Ranked-book | **MISSING** | `rank_order` / `ranking_vector` only | `rank_review_rows` is synchronous in `/opportunities/summary` with no `ranked_at_ns`. |
| API response | **MISSING** | `as_of_context.as_of_time` is store as-of | Operating context has `as_of_time` string, **not** HTTP `generated_at_ns`. Optional hot-path `note_operator_surfaced` uses **process monotonic** at serialize — not in the payload, not wall, not UI. |
| UI first-visible | **MISSING** | none | Opportunity client/schema has no first-paint / first-visible clock. `AttentionItem.surfaced_time` is attention source-time, not cockpit first paint. |
| Operator action | **AMBIGUOUS** | `opportunity_operator_acks.created_at_ns`; `ExecutionDecisionTraceV1.decision_time_ns` | Ack path stamps `as_of_context["as_of_time_ns"]`, but `build_operating_context` **does not emit** `as_of_time_ns` (falls through to `0`). Trace `SURFACE` is **detail fetch**, not first-visible; WATCH/DISMISS use the same as-of stamp. Fields exist; they are not operator wall-clock. |

## Target next-RTH deltas

| Delta | Class | How to compute honestly | Blocker |
|---|---|---|---|
| source→receive | **DERIVABLE** | `published_time` (quality `KNOWN`) → `retrieved_time` or `EventV1.received_time_ns` | Unknown publication; EventV1 without news mapper; Finviz discovery `event_time_ns` is not publication |
| receive→normalization | **AMBIGUOUS** | Would be receive → **processed** time | `available_time_ns` is the wrong right-hand clock |
| normalization→detector | **AMBIGUOUS** | Needs processing-complete → detector complete **and** `source_event_refs` join | Decision-time stamps; news path not correlated |
| detector→opportunity | **AMBIGUOUS** | `detected_at_ns` → `created_at_ns` when lineage joins | Both are decision times; may be equal; software-wired merge is not lineage |
| opportunity→UI | **MISSING** | Opportunity create → UI first-visible | No first-visible; API serialize ≠ UI |
| UI→operator | **MISSING** | First-visible → operator wall-clock ack | No first-visible; ack clock is as-of/`0` |
| source→operator total | **AMBIGUOUS** | Sum of honest hops, or published → operator wall-clock | Operator wall-clock not currently stamped; do not use as-of/`0` |

Existing hot-path software segments (`imp_receive_to_normalized`, `normalized_to_router_dispatched`, `detected_to_opportunity_created`, `opportunity_created_to_operator_surfaced`) are **fixture software-wired**, not next-RTH. Several use the wrong clock kinds above. Replay baseline still reports `opportunity_created_at` / `operator_surfaced_at` as `NOT_EXERCISED` on the capture fixture.

## What already exists (reuse, do not replace)

- **News clocks:** `published_time` vs `retrieved_time` are deliberately split ([`news/contracts.py`](../../../src/market_platform_foundation/news/contracts.py), [`news/timestamps.py`](../../../src/market_platform_foundation/news/timestamps.py)).
- **EventV1 clocks:** `event_time_ns`, `available_time_ns`, optional `provider_time_ns`, optional `received_time_ns` plus `ProviderProvenance.availability`.
- **Ingress:** `IngressDispatchReceiptV1.dispatch_time_ns` (often passed as `event.available_time_ns` today — same conflation).
- **Opportunity / ranking:** `created_at_ns`, `rank_order`; no ranked/API/UI stamps.
- **DecisionTrace:** `decision_time_ns` + `SURFACE` / `WATCH` / `DISMISS` kinds; observability only.
- **Hot-path collector:** in-memory `HotPathClockRow`; missing fields stay `None` (never zero-fill). Join across stages is still demo-merge in `software_wired.py`.
- **RT-01:** process monotonic vs wall helpers; ingest-path spans are a **different** pipeline (quotes/depth), not news→OE.

## Minimal telemetry patch plan (unmerged; P1 owns schema)

Do **not** add EventV1 fields, ranked-book payload keys, or UI schema fields in this lane. Prefer wiring and honest labels.

### A. Wiring only (no production schema) — recommended for next-RTH

1. **Map news clocks into `HotPathClockRow` without EventV1 mutation.** `source_event_at` ← `published_time` only when `published_time_quality == KNOWN`; else `None`. `imp_received_at` ← `retrieved_time` / `received_time_ns`. Leave `provider_received_at` `None` unless a vendor index clock is actually present.
2. **Stop using `available_time_ns` as `normalized_at`.** Stamp `normalized_at` with `wall_time_ns()` at adapter return (side collector only). Keep `available_time_ns` as eligibility.
3. **Join on lineage, never first-row merge.** Detector rows via `DetectionV1.source_event_refs`; opportunity via `OpportunityV1.lineage_refs` / `source_event_id`. If join fails, leave the hop `NOT_EXERCISED`.
4. **Label `operator_surfaced_at` as API serialize** (`OPERATOR_SURFACED_API_SERIALIZE`), not UI first-visible. Still process-monotonic unless switched to `wall_time_ns()` in the collector.
5. **Operator action wall-clock** belongs in `apply_opportunity_ack` (`monotonic_wall_ns()` into `created_at_ns` / trace `decision_time_ns`). That file is **P1/other-lane owned** — do not edit here. Keep using DecisionTrace kinds.

### B. P1 production schema (document only — do not edit)

Only if next-RTH must persist hops on contracts/API:

| Change | Owner | Why not this lane |
|---|---|---|
| `EventV1.normalized_at_ns` / processed-time field | P1 EventV1 | Optional field; current four clocks already cover source/receive/available |
| NewsArticleEvent → EventV1 mapper clock mapping | other lane | Explicitly out of P6 ownership |
| `ranked_at_ns` / `generated_at_ns` on `/opportunities/summary` | P1 UI API schema | Would change Zod/contracts; as-of must stay as-of |
| UI `first_visible_at_ns` | P1 UI | Client paint is not authority; optional later |
| Ack `created_at_ns` semantic change (as-of → wall) | other lane (`opportunity_projections.py`) | Behavior + possibly operator-ack interpretation |

**Do not** add a new telemetry backend, span store, or required hot-path write per tick ([observability hot-path protection](../../platform/OBSERVABILITY_STANDARD.md)).

### C. Honesty rules for any next-RTH capture

- Missing pairs stay missing (`missing_pair_count`); never invent 0.
- MEASURED only when `present_count > 0` (existing `derive_timestamp_exercise`).
- Do not treat RTH empirical ops `timing_ns` (dry-run copies `operator_surfaced_at` into `imp_received_at`) as source→operator evidence.
- Do not edit frozen FTEP RTH artifacts.

## Helper

Diagnostic catalog + delta helper (no production emission):

`src/market_platform_foundation/hot_path_telemetry/next_rth_latency_audit.py`

Tests: `tests/hot_path_telemetry/test_next_rth_latency_audit.py` (picked up by existing `hot_path_telemetry` suite globs).

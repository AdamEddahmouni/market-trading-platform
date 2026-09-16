# UIR-01 — Current-Contract Operator UI Redesign

**Status:** Active implementation note. Increment A+B landed on
`ui/operator-redesign-current` (PR #226); Increment C landed on
`ui/operator-redesign-command-convergence`.
**Scope:** Increment A (design system + shell + navigation) and Increment B
(Discover/Radar + opportunity state/evidence presentation) on top of current
canonical contracts at `origin/main` (`42b1237a`). Increment C (Command /
Paper-Now convergence on the Radar opportunity language, provider-health
semantic routing, mobile Radar detail sheet) on `21ab1ac1`.
**Design guidance:** `docs/ui-redesign-v2/` (recovered RTH15-00 plans) is used as
design guidance only. The stale `ui/operator-redesign-v2` branch was read as
reference (`git show`) and was **not** used as an implementation base.

---

## 1. Current contract map (operator-facing)

Source of truth: `ui/src/api/schemas.ts`, `ui/src/api/opportunityClient.ts`,
`ui/src/api/hooks.ts`. The UI presents these contracts; it does not invent shapes.

### 1.1 Opportunity summary — `GET /opportunities/summary`

`OpportunitiesSummaryResponseSchema`:

| Field | Meaning | Optionality | Operator relevance |
|---|---|---|---|
| `as_of_context` | Mode/data-mode/authority/as-of triple + timezone | required | Global honesty anchor (StatusBar) |
| `quality_summary.state` | Feed-side quality vocabulary (free string) | required | Data-health pill |
| `feed_status` | `READY` / `UNREADY` / `EMPTY` / `UNAVAILABLE` (observed values; free string) | required | Queue availability; drives empty/unready states |
| `reason` / `unready_reason` | Backend reason code/text for non-READY | optional | Humanized via adapter; raw in L4 |
| `next_action` | Operator next action (may be a path) | optional | Banner action link target |
| `items` | `OpportunityReviewRow[]` | required | The ranked queue |
| `next_cursor` | Pagination | nullable | Not yet used by UI |

### 1.2 Opportunity row — `OpportunityReviewRowSchema` (passthrough)

| Field | Meaning | Optionality | Freshness semantics | Operator relevance |
|---|---|---|---|---|
| `summary_id` | Stable row identity (summary level) | required | — | Row key; ack target |
| `instrument_id` | Canonical instrument | **nullable** | — | Absent → workspace action hidden, "Instrument unavailable" |
| `headline` | Human-readable "what/why now" | required | — | Primary L1 text |
| `opportunity_id` | OpportunityV1 identity | nullable | — | Present ⇒ `identity_kind=OPPORTUNITY_V1` |
| `identity_kind` | `OPPORTUNITY_V1` or other (free string) | optional | — | Contract vs non-contract row |
| `eligibility_state` | e.g. `INELIGIBLE`, `NORMALIZED_AWAITING_FORECAST` | nullable | — | `INELIGIBLE` ⇒ STOP, ack blocked |
| `lifecycle_state` | Lifecycle (e.g. contains `EXPIRED`) | nullable | stale-ish semantics | Presentation state derivation |
| `next_safe_action` | `OPEN_WORKSPACE` / `STOP` / `NONE` (observed) | optional | — | Primary action gate |
| `rank_order` | 1-based rank | nullable | — | `#n` label |
| `unavailable_fields` | Fields the backend could not produce | optional | — | Honesty: shown as unavailable, never fabricated |
| `explanation_ref` | `explain:…` ref for the drawer | optional | — | Explain action |
| `ranking_vector` | `{ basis, dimensions[{name,status,value,unit,reason_code}], rank_order }` | nullable | — | Evidence strength; `basis != COMPARATOR_LEXICOGRAPHIC` ⇒ provisional order banner |
| `data_quality` | Record; observed keys `status`, `freshness`, `source` | nullable | `freshness` carries the backend freshness word | Freshness + quality pills |
| `decision_support` | `{ authority, kill_switch, reason_codes, … }` passthrough | optional | — | Risk overlay display only (never ranking) |
| passthrough extras (`evidence_class`, `created_at_ns`, `expires_at`, `supersession_reason`, `duplicates`, `metadata.agent_enrichment`, `edge_stats_artifact`, …) | Used by `progressiveOpportunityModel.ts` | optional | `created_at_ns` → age | L2/L3 detail sections |

### 1.3 Opportunity evidence — `GET /opportunities/{summary_id}/evidence`

`OpportunityEvidenceResponseSchema` (passthrough): `evidence_class`,
`evidence_promotion_reason`, `family_admission_status/reason`, `data_quality`,
`ranking_basis`, `created_at_ns`, `duplicates[]`, `supersession_reason`,
`unavailable_fields[]`, `lineage_refs[]`, `research_artifact_evidence`
(`authority_class` e.g. `EVIDENCE_NOT_PREDICTION`, `readiness`, `attachments[]`).

### 1.4 Opportunity ack — `POST /opportunities/{summary_id}/{watch|dismiss|review}`

Paper-gated in UI (`paperActions` + not INELIGIBLE/STOP). Observational operator
lifecycle only; no execution authority. Invalidates `opportunitiesSummary`.

### 1.5 Mixed screener — `/discover/mixed` (raw fetch, hand-typed in `DiscoverObservability.tsx`)

`MixedPayload`: `available`, `mode=SEMI_LIVE`, `candidate_role=INVESTIGATE`,
`execution_authority=NONE`, `market_session`, `generated_at`, `discovery_as_of`,
`candidate_count`, `refresh_in_progress`, `refresh_interval_seconds` (default 120),
`poll_interval_seconds` (default 3), `provider_health[]`, `lane_counts`,
`screen_outcomes[]`, `candidates[]` (`instrument_id`, `lanes`, `screen_matches`,
`matched_reasons`, `metrics{change_pct,rel_volume,…}`, `quality`,
`attention_score`, `ranking_reasons[]`, `supporting_evidence[]`, `caveats[]`,
`market{provider,status:LIVE|DELAYED|SNAPSHOT|STALE|UNAVAILABLE,last_price,…}`,
`data_status` same vocabulary, `freshness_label`, `queue_rank`).

**Preserved contracts (fragile):** unmount `POST /discover/mixed/release`
(`keepalive`), server-driven poll/refresh timers paused on `document.hidden`,
Paper-only `POST /discover/mixed/refresh` and `POST /discover/promote-to-live-analysis`,
mutating `GET /discover/run?force=1` (documented debt, not hardened here).

### 1.6 Context — `GET /context`

`ContextResponseSchema`: `as_of_context` (`mode`, `data_mode`, `execution_mode`,
`execution_authority`, `as_of_time`, `timezone`, …), `capability_states[]`,
`quality_summary{state,detail,affected_symbols}`, `scope_symbols`,
`active_instrument`. Drives `evaluateModeContext` / `hasPaperAuthority` /
`canUsePaperActions` (`ui/src/components/mode-session/modeAuthority.ts`) — gating
logic unchanged by this redesign.

### 1.7 State vocabularies mapped by the adapter

- **Feed:** `READY`/`UNREADY`/`EMPTY`/`UNAVAILABLE` (+ unknown → neutral).
- **Freshness (OE G7 binding):** `FRESH`/`STALE`/`UNKNOWN`/`NOT_APPLICABLE` +
  screener `data_status` (`LIVE`/`DELAYED`/`SNAPSHOT`/`STALE`/`UNAVAILABLE`).
- **Eligibility/action:** `INELIGIBLE`, `NORMALIZED_AWAITING_FORECAST`,
  `OPEN_WORKSPACE`, `STOP`, `NONE`.
- **Mode/session/authority:** `DEMO`/`PAPER`/`LIVE`; `FIXTURE_REPLAY`,
  `HISTORICAL_CAPTURE`, `LIVE_OBSERVATIONAL`, `BROKER_DELAYED`; `NONE`,
  `INTERNAL_SIMULATION`, `BROKER_PAPER`, `LIVE`; `BLOCKED`, `PAPER_ONLY`,
  `AUTHORIZED`.
- **Data health:** `GOOD`/`PASS`/`PARTIAL`/`DEGRADED`/`STALE`/`UNAVAILABLE`/
  `UNKNOWN`/`DISCONNECTED`/`RESTORED` (union of both backend vocabularies).
- **Error categories:** the twelve `CanonicalErrorCategory` values (STALE_DATA/
  RATE_LIMITED/TIMEOUT → caution; VALIDATION_ERROR → neutral; rest → critical;
  unknown → critical fail-closed, matching `errors.ts`).
- **Presentation state (client-derived, documented):** `DETECTED`/`PROVISIONAL`/
  `VERIFYING`/`VERIFIED`/`CONTRADICTED`/`EXPIRED` from
  `derivePresentationState` — derived only from backend fields, never new truth.

Unknown/unmapped values render `neutral` + raw string in a detail surface + dev
warning. Never a guessed sentence; never a throw.

## 2. Target information architecture (this increment)

Primary nav (operator mental model):

| # | Label | Route | Notes |
|---|---|---|---|
| 1 | Command | `/` | Now desk; **Signals** becomes a tab (`/?desk=signals`); `/signals` redirects |
| 2 | Radar | `/radar` | Canonical discovery queue; `/discover` redirects; `/explore` → `/radar/screeners` |
| 3 | Workspace | `/workspace` | Decision cockpit (Paper submit boundary) — unchanged |
| 4 | Portfolio | `/portfolio` | Unchanged |
| 5 | Research | `/research` | GATED badge removed (no gate logic exists) |
| 6 | Control | `/control` | Renamed from "Risk" (route unchanged) |

Operator group (unchanged targets): Live Canary `/live-canary`, Settings
`/settings`, Diagnostics `/diagnostics/provider`. `/lab` still redirects to
`/research` (real Lab page is a later increment). Mode stays session-scoped
React state (not URL). Redirects use `<Navigate replace>`; old deep links land.

Radar tabs: **Opportunities** (`/radar`) = ranked OE queue + selected
opportunity detail + mixed live screener (today's `/discover` composition).
**Screeners** (`/radar/screeners`) = donor research bridges (today's `/explore`
composition per mode).

## 3. Design system (this increment)

- `tokens.css`: 7 semantic state tones × fg/bg/border, spacing scale
  (4/8/12/16/24/32), radii (4/6/10), type scale (11px floor), layout constants,
  chart tokens; 9 previously-undefined vars defined as aliases; AA contrast
  fixes (`--text-muted #6b7280 → #8b94a5`, `--direction-short #c44e52 → #d96368`).
- `ui/src/state/semanticState.ts`: pure adapter `resolveSemanticState(domain,
  raw, options?)` — single entry point for enum/state rendering.
- `ui/src/components/imp-ui/`: `StatePill`, `AttentionBanner` (3-question slots),
  `FreshnessIndicator`, `ConfidenceIndicator`, `ErrorState`, `EmptyState`
  (reason mandatory), `Tabs` (ARIA pattern, routable variant), plus `imp-ui.css`.
- Shell: `StatusBar` consolidates `ModeEnvironmentBar` + `ContextBar` into one
  40px bar (ModeBadge sentence, authority, data health + freshness, scope,
  as-of human time; raw triple behind L4 details). `ImpContextTrustLayer`
  (capability strip + provider matrix drawer) is preserved below it.
- Nav: `NavShell` rebuilt to the IA above; current-section visibility; per-mode
  hints kept; `aria-label` pattern kept.

## 4. Page contracts (changed surfaces)

### Radar — Opportunities (`/radar`)
- **Operator question:** What opportunities exist, ranked — why now, how strong,
  how fresh, what state, what next?
- **Primary action:** select a row → inspect detail; `Open workspace` when
  `next_safe_action=OPEN_WORKSPACE` and instrument present.
- **L1:** queue (rank, symbol, what/why-now, state, evidence strength,
  freshness, next action) + selected card decision summary.
- **L2 (disclosure):** evidence & verification (dimensions, provenance, quality,
  timestamps, contradictions).
- **L3 (disclosure):** historical/research context, trade review.
- **L4 (disclosure):** raw IDs, ranking vector, data_quality JSON.
- **States:** loading skeleton; UNREADY → AttentionBanner (human reason +
  Control action); EMPTY → why-empty; error → ErrorState with retry; Live
  UNAVAILABLE → by-design explanation.
- **Responsive:** ≥1024 split queue+detail; <1024 the queue stays scannable and
  the selected opportunity opens in an overlay detail sheet (backdrop, focus
  trap, Escape/close, scroll lock; full-screen below 720px).

### Increment C — one opportunity language (landed)

- Shared module `ui/src/components/opportunity/`: `opportunityPresentation.ts`
  (stable key, presentation-state derivation, state label/tone maps, evidence
  input summaries, eligibility/workspace/ack predicates, next-action
  resolution — the single copy), `opportunityDetailModel.ts` (L1–L4 detail
  sections), `OpportunityCard` (compact queue card), `OpportunityQueue` +
  `OpportunityFeedState` (one feed-state presentation: loading / error+retry /
  UNREADY banner / UNAVAILABLE / empty-why).
- Command overview (`ImpOverviewPrimaryQueue`) and Radar render the same
  state/evidence/freshness/next-action primitives; Command stays compact and
  leads into Radar for deep detail.
- Paper-Now: candidate queue holds attention **signals** (not opportunities);
  the dead embedded opportunity list was removed. Header account/session IDs
  use `CopyableIdentifier`; execution mode/authority and data health render
  through `resolveSemanticState`. Action gating unchanged (Workspace remains
  the only submit boundary; preview composer authority check untouched).
- Provider health: `LiveProviderRibbon`, the Live header, and Live KPI strip
  route connection/channel/authority states through the semantic adapter
  (healthy/degraded/stale/unavailable/unknown tones; no synthetic scores).
  `/diagnostics/provider` stays the raw L4 technical surface by design.
- Retired: `ProgressiveOpportunityCard`, `now/OpportunityReviewCard(.test)`,
  `OpportunityFeedStatusBanner`(+test), `impOpportunityDisplay.ts`
  (`opportunityTags` was dead), legacy `progressive-opp-*`/review-list CSS.
  The detail model/fixtures moved to `opportunity/` (renamed, behavior kept).

### Radar — Screeners (`/radar/screeners`)
- Today's `/explore` per-mode content; headline/label mismatches resolved
  ("Screeners", not "Markets"/"Explore" split-brain).

### Command (`/`)
- Desk tabs (Overview | Signals) wired to `?desk=`; layouts per mode unchanged.
- Increment C (above) converged the overview queue onto the shared opportunity
  primitives; the deeper Command rebuild remains future work.

## 5. Explicitly preserved

- `canUsePaperActions` / `evaluateModeContext` gating; Workspace as the only
  Paper submit boundary; preview revalidation semantics; ack gating
  (`INELIGIBLE`/`STOP` block acks); Live = zero mutations; Demo read-only.
- Discover mixed-screener mutations, unmount release POST, 3s/120s timers,
  visibility pause.
- React Query keys and cadences; no new endpoints; no invented fields.
- `App.test.tsx` updated for route/nav changes (standing obligation C6).

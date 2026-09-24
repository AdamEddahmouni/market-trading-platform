# Semantic State System

THE canonical semantic model for the redesign. One adapter, one set of tones, one
language layer. The UI **translates, never invents**: every rendered state comes from
`resolveSemanticState(domain, rawValue)`; unmapped/unknown values render `neutral`
with the raw string preserved in a detail surface — never a guessed sentence.

- Adapter module (to be created): `ui/src/state/semanticState.ts`
- Adapter signature:

```ts
type SemanticTone = "live" | "paper" | "replay" | "research" | "caution" | "critical" | "neutral";

type SemanticState = {
  tone: SemanticTone;
  label: string;          // short human label, e.g. "Paper orders only"
  sentence?: string;      // full human sentence for banners/L1, e.g. "Market data is stale — quotes may be delayed."
  affects?: string;       // 3-question rule: what it affects
  action?: { label: string; href?: string };  // 3-question rule: what to do
  raw: string;            // original backend value, always preserved for L4
};

resolveSemanticState(domain: StateDomain, rawValue: string | undefined | null): SemanticState;
```

---

## 1. Semantic tones (7)

| Tone | Meaning | Token triple | Proposed values (verify contrast with tooling; targets ≥ 4.5:1 fg on `--surface-0`) |
|---|---|---|---|
| `live` | LIVE OBSERVATION — real-time market data flowing | `--imp-state-live-fg` / `-bg` / `-border` | `#3dd68c` / `rgba(61,214,140,0.10)` / `rgba(61,214,140,0.35)` |
| `paper` | PAPER / SIMULATION — simulated execution, paper authority | `--imp-state-paper-fg` / `-bg` / `-border` | `#ff8a00` / `rgba(255,138,0,0.10)` / `rgba(255,138,0,0.35)` |
| `replay` | REPLAY — historical/fixture playback | `--imp-state-replay-fg` / `-bg` / `-border` | `#a78bfa` / `rgba(167,139,250,0.10)` / `rgba(167,139,250,0.35)` |
| `research` | RESEARCH — interpretation, models, non-tradeable evidence | `--imp-state-research-fg` / `-bg` / `-border` | `#8ba3c7` / `rgba(139,163,199,0.10)` / `rgba(139,163,199,0.30)` |
| `caution` | DEGRADED / CAUTION — working but impaired, stale, partial | `--imp-state-caution-fg` / `-bg` / `-border` | `#d4a017` / `rgba(212,160,23,0.10)` / `rgba(212,160,23,0.35)` |
| `critical` | BLOCKED / FAILURE / CRITICAL — action required or hard stop | `--imp-state-critical-fg` / `-bg` / `-border` | `#e36d77` / `rgba(227,109,119,0.10)` / `rgba(227,109,119,0.35)` |
| `neutral` | NEUTRAL / HISTORICAL / INFO — no urgency, off, unknown | `--imp-state-neutral-fg` / `-bg` / `-border` | `#9aa3b5` / `rgba(154,163,181,0.08)` / `rgba(154,163,181,0.25)` |

Usage rules:
- Every tone renders with text and/or icon — **never color alone** (a11y hard rule).
- `-bg` is for badges/pills/banners; `-border` for card/row accents; `-fg` for text
  and icons. Do not use state colors for non-state decoration.
- `paper` intentionally reuses the IMP orange family: the brand accent and the paper
  simulation tone are the same identity ("simulation is IMP's home mode").
- Legacy aliases for migration: `--warning` → `--imp-state-caution-fg`;
  `--danger` → `--imp-state-critical-fg`; `--direction-long` stays for market
  direction (long/up) and is **not** a state token; `--direction-short` (contrast-fixed)
  stays for short/down. Direction ≠ state: a price being down is not a failure.

## 2. State domains

| Domain key | Covers | Primary sources (audit 03) |
|---|---|---|
| `mode` | UI mode, backend mode label, mode alignment | `selectedMode`, `/context as_of_context.mode`, `evaluateModeContext` |
| `session` | Replay session, paper session, auth session, canary session, startup/crash recovery | `/replay/session`, `/paper/portfolio session`, `/auth/*`, `/canary/snapshot`, `/state/startup` |
| `executionAuthority` | Execution mode, authority, eligibility, order preview/risk gates | `/context as_of_context`, portfolio `account`, preview payload |
| `providerHealth` | Provider connection state, channel health, provider readiness | `/provider/health`, `/operator/readiness`, `/discover/mixed provider_health[]` |
| `dataHealth` | Quality summary (both vocabularies), portfolio data health, mark quality, discover data status, lane quality/freshness | `/context quality_summary`, `/paper/portfolio data_health`, positions `mark_quality`, `/discover/mixed`, workspace evidence lanes |
| `portfolio` | Order states, reconciliation, kill switches, settlement, risk decisions | `/paper/portfolio`, `/paper/order-history`, `/canary/snapshot`, `/paper/strategy-profitability` |
| `research` | Epistemic class, authority boundary, opportunity feed/lifecycle, evidence coherence | `/research/*`, `/opportunities/*`, workspace evidence |

## 3. Enum → tone/language mapping tables

Every backend enum vocabulary from audit 03. "Template" is the human language; `{x}`
are payload values. Raw value always available via `state.raw` for L4.

### 3.1 Domain `mode`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| UI `DEMO` | `replay` | "Demo replay" / "Demo replay — trading disabled. Recorded market data." |
| UI `PAPER` | `paper` | "Paper trading" / "Paper trading active — simulated fills, no real money." |
| UI `LIVE` | `live` | "Live observation" / "Live market data — read-only, execution locked." |
| backend `mode: LIVE` | `live` | "Live" |
| backend `mode: REPLAY` | `replay` | "Replay" |
| backend `mode: SIMULATION` | `paper` | "Simulation" |
| backend `mode: PAPER` | `paper` | "Paper" |
| mode alignment `compatible` | `live` | "Backend aligned" |
| mode alignment `mismatch` | `critical` | "UI and backend disagree" / "You selected {mode}, but the backend reports {human data/exec/auth}. UI mode selection does not change backend authority. Switch mode or restart the backend session." |
| mode alignment `unavailable` | `caution` | "Backend context unavailable" / "Backend context unavailable. Execution controls remain locked. Check the local platform in Control, then retry." |

### 3.2 Domain `session`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| `data_mode: FIXTURE_REPLAY` | `replay` | "Demo replay (recorded data)" |
| `data_mode: HISTORICAL_CAPTURE` | `replay` | "Historical capture (recorded data)" |
| `data_mode: LIVE_OBSERVATIONAL` | `live` | "Live market data · {provider}" |
| `data_mode: BROKER_DELAYED` | `caution` | "Delayed broker data — quotes may lag" |
| crash recovery `OPEN_SESSION_DETECTED` | `caution` | "Previous paper session detected" / "A previous paper session was restored. Positions rebuild from events; live marks wait for fresh data. No action needed." |
| crash recovery `CORRUPT_DB` | `critical` | "Local state database failed integrity check" / "The local state database failed an integrity check. The original file was preserved at {path}. Trading state may be incomplete — review Settings → State." |
| paper session `OPEN` | `paper` | "Paper session open · started {date}" |
| paper session `CLOSED`/archived | `neutral` | "Session closed {date}" |
| canary `session_state` (free string) | map via kill-switch rule | humanized; raw in Audit details |

### 3.3 Domain `executionAuthority`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| `execution_mode: NONE` | `neutral` | "No execution" |
| `execution_mode: INTERNAL_SIMULATION` | `paper` | "Paper trading (simulated fills)" |
| `execution_mode: BROKER_PAPER` | `paper` | "Broker paper trading" |
| `execution_mode: LIVE` | `critical` | "LIVE EXECUTION — real money" (exceptional in this UI; always paired with the critical banner idiom) |
| `execution_authority: BLOCKED` | `neutral` | "No trading authority" |
| `execution_authority: PAPER_ONLY` | `paper` | "Paper orders only" |
| `execution_authority: AUTHORIZED` | `caution` | "Execution authorized" (elevated attention: broader than paper) |
| eligibility `DISPLAY_ONLY` | `neutral` | "Market data only — cannot route orders" |
| eligibility `INTERNAL_PAPER_ELIGIBLE` | `paper` | "Eligible for paper simulation" |
| preview `risk_status: PASS` | `live` | "Preview passed risk checks" |
| preview `risk_status: BLOCKED` | `critical` | "Blocked by risk: {reason_codes humanized}" |
| preview `decision: APPROVE` | `live` | "Approved" |
| preview `decision: RESIZE` | `caution` | "Approved with reduced size" |
| preview `decision: REJECT` | `critical` | "Rejected" |
| preview `quality_state: PASS` | `live` | "Preview current" |
| preview `quality_state: WAITING_FOR_ELIGIBLE_LIVE_EVENT` | `caution` | "Waiting for a fresh market event — preview may be stale" |
| preview `quality_state: NO_EXECUTABLE_BAR` | `caution` | "No executable price bar — preview is indicative only" |
| revalidation `PREVIEW_EXPIRED` | `caution` | "Preview expired — re-preview before submitting" |
| revalidation `PREVIEW_INTENT_MISMATCH` | `critical` | "Order changed since preview — re-preview required" |
| revalidation `PREVIEW_PORTFOLIO_STALE` | `caution` | "Portfolio changed since preview — re-preview required" |
| revalidation `PREVIEW_POLICY_STALE` | `caution` | "Risk policy changed since preview — re-preview required" |
| revalidation `PREVIEW_MARGIN_STALE` | `caution` | "Margin data changed since preview — re-preview required" |
| revalidation `PREVIEW_REQUIRED` | `critical` | "A current preview is required before submitting" (fail-closed guard) |
| preview presentation `NOT_PREVIEWED` | `neutral` | "Not previewed yet" |
| preview presentation `PREVIEWING` | `neutral` | "Previewing…" |
| preview presentation `ACCEPTED` | `live` | "Preview accepted — ready to submit" |
| preview presentation `REJECTED` | `critical` | "Preview rejected" |
| preview presentation `REVALIDATION_REQUIRED` | `caution` | "Re-preview required" |
| preview presentation `AUTHORITY_UNAVAILABLE` | `critical` | "Trading authority unavailable — ticket locked" |
| preview presentation `ERROR` | `critical` | "Preview failed: {humanized error}" |

### 3.4 Domain `providerHealth`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| connection `CONNECTED` | `live` | "{Provider} — connected" |
| connection `CONNECTED_DEGRADED` | `caution` | "{Provider} — connected with problems" |
| connection `DEGRADED` | `caution` | "{Provider} — degraded" |
| connection `CONNECTING` / `RECONNECTING` | `neutral` | "{Provider} — connecting…" / "reconnecting…" |
| connection `DISCONNECTED` | `critical` | "{Provider} — disconnected" |
| connection `ERROR` | `critical` | "{Provider} — error: {last_error humanized}" |
| connection `DISABLED` | `neutral` | "{Provider} — disabled" |
| connection `ENTITLEMENT_MISSING` | `neutral` | "{Provider} — not in your subscription" |
| channel `HEALTHY` | `live` | "Working" |
| channel `DEGRADED` | `caution` | "Degraded — {channel} may lag" |
| channel `UNAVAILABLE` | `neutral` | "Not available with your current data subscription" (adds affect: "this lane/feature is disabled") |
| readiness `READY` | `live` | "Ready" |
| readiness `ACTION_REQUIRED` | `caution` | "Action required: {next_action}" |
| credential `CONFIGURED` | `live` | "Credentials configured" |
| credential `MISSING` | `caution` | "Credentials missing — {next_action}" |
| credential `NOT_REQUIRED` | `neutral` | "No credentials required" |
| gate `ENABLED` | `live` | "Enabled" |
| gate `DISABLED` | `neutral` | "Disabled" |
| gate `CONFIGURED` | `live` | "Configured" |
| gate `OPTIONAL` | `neutral` | "Optional" |
| transport `IMPLEMENTED*` / `HTTPS_PAPER_HOST` / `COMPARATOR_NOT_CONFIGURED` | `live` | "Available" (variant detail in TechnicalDetails) |
| transport `FIXTURE_ONLY` | `replay` | "Fixture data only" |
| transport `UNAVAILABLE` | `critical` | "Unavailable" |
| transport `BLOCKED_NON_LOOPBACK` | `critical` | "Blocked — non-loopback address refused" |

### 3.5 Domain `dataHealth`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| quality `GOOD` / `PASS` | `live` | "Market data healthy" |
| quality `PARTIAL` | `caution` | "Market data is partial — some sources unavailable" |
| quality `DEGRADED` | `caution` | "Market data is degraded — {affected surfaces}" |
| quality `STALE` | `caution` | "Market data is stale — quotes may be delayed" |
| quality `UNAVAILABLE` | `critical` | "Market data unavailable — {what to do}" |
| portfolio `data_health: PASS` | `live` | "Mark data current" |
| portfolio `data_health: UNKNOWN` | `neutral` | "Mark data quality unknown" |
| portfolio `data_health: STALE` | `caution` | "Mark data is stale — unrealized P&L may be inaccurate" |
| portfolio `data_health: DISCONNECTED` | `critical` | "Mark data disconnected — P&L is not updating" |
| portfolio `data_health: RESTORED` | `caution` | "Session restored — marks wait for fresh data" |
| position `mark_quality` | same map as portfolio `data_health` | "Price stale · last updated {relative}" etc. |
| discover `data_status: LIVE` | `live` | "Live" |
| discover `data_status: DELAYED` | `caution` | "Delayed" |
| discover `data_status: SNAPSHOT` | `neutral` | "Snapshot (point-in-time)" |
| discover `data_status: STALE` | `caution` | "Stale" |
| discover `data_status: UNAVAILABLE` | `critical` | "Unavailable" |
| lane `quality` (per-lane evidence) | map via quality vocabulary above | per-lane sentence + `freshness_label` → FreshnessIndicator |
| lane provenance stale (client 5-min threshold) | `caution` | "Lane evidence is stale — last updated {relative}" |

Note: `quality_summary.state` has **two backend vocabularies** (replay:
GOOD/PARTIAL/DEGRADED/STALE/UNAVAILABLE; live override: PASS/UNAVAILABLE/STALE/
DEGRADED). The adapter maps the union; it does not care which produced the value.
`workspaceHealth.formatDataHealthLabel`'s `CAPTURE_REPLAY` branch is dead (not a
backend value) — the adapter replaces that helper; `HISTORICAL_CAPTURE` renders
"Historical capture", never the raw underscore string.

### 3.6 Domain `portfolio`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| order `FILLED` | `live` | "Filled" |
| order `CANCELLED` | `neutral` | "Cancelled" |
| order `EXPIRED` | `neutral` | "Expired" |
| order `REJECTED` | `critical` | "Rejected" |
| order `RISK_REJECTED` | `critical` | "Rejected by risk controls" |
| order open/working (untyped others) | `paper` | "Working" (raw state in details) |
| reconciliation ok-set (`PASS`, `HEALTHY`, `CLEAN`, `RECONCILED`, `INTERNAL_AUTHORITATIVE`) | `live` | "Reconciled" |
| reconciliation anything else | `caution` | "Reconciliation needs attention: {raw}" |
| kill switch `OFF` / `INACTIVE` / `CLEAR` | `live` | "Kill switch: off" |
| kill switch anything else | `critical` | "Kill switch: ON — {scope} trading halted" |
| `broker_health` / `reconciliation_health` ok-set (`HEALTHY`, `OK`, `PASS`, `+RECONCILED`) | `live` | "Broker connection: healthy" / "Reconciliation: healthy" |
| …anything else | `caution` | "…needs attention: {raw}" |
| settlement `SETTLED` | `live` | "Settled" |
| settlement `PENDING` | `caution` | "Settlement pending" |
| settlement `UNAVAILABLE` | `neutral` | "Settlement unknown" |
| risk decision ok-set (`PASS`, `ALLOW`, `APPROVE`, `RESIZE`) | `live` | humanized decision |
| risk decision problem regex (`BLOCKED|REJECTED|WAITING|FAILED`) | `critical` | humanized decision + reason codes |
| order side `BUY` / `SELL` | direction tokens (not state) | "Buy" / "Sell" |
| order type `MARKET` / `LIMIT` | `neutral` | "Market" / "Limit" |

### 3.7 Domain `research`

| Backend value | Tone | Label / sentence template |
|---|---|---|
| epistemic `OBSERVED` | `live` | "From provider data" |
| epistemic `DERIVED` | `research` | "Calculated by IMP" |
| epistemic `INFERRED` | `caution` | "IMP inference — unverified" |
| `authority_boundary: RESEARCH_ONLY` | `research` | "Research-only evidence — not tradeable" |
| `authority_boundary: PAPER_OBSERVABILITY(_READ_ONLY)` | `paper` | "Paper simulation observability — read-only" |
| opportunity `feed_status: READY` | `live` | "Radar ready" |
| opportunity `feed_status: UNREADY` | `caution` | "Opportunity radar isn't ready: {humanized unready_reason}" + action link |
| opportunity `feed_status: EMPTY` | `neutral` | "No opportunities right now — {why: filters/coverage}" |
| opportunity `feed_status: UNAVAILABLE` | `critical` | "Opportunity feed unavailable" (in LIVE mode: "Live mode has no opportunity engine — use Radar screeners and workspace evidence") |
| opportunity `feed_status: DISMISSED` | `neutral` | "Dismissed" |
| opportunity `next_safe_action: OPEN_WORKSPACE` | — | CTA "Open workspace" |
| opportunity `next_safe_action: STOP` | `critical` | "Stop — do not act on this opportunity" |
| opportunity `next_safe_action: NONE` | `neutral` | "No action" |
| opportunity `eligibility_state: INELIGIBLE` / `UNAVAILABLE` | `neutral` | "Not eligible" / "Unavailable" |
| opportunity `eligibility_state: NORMALIZED_AWAITING_FORECAST` | `caution` | "Awaiting forecast" |
| sentiment `positive` / `negative` / `neutral` / `mixed` / `unknown` | direction/neutral | "Positive" / "Negative" / "Neutral" / "Mixed" / "Unknown" |
| evidence `data_mode: frozen` | `replay` | "Frozen research snapshot" |
| evidence `data_mode: current` | `live` | "Current data" |

### 3.8 Cross-cutting

| Vocabulary | Tone rule | Language rule |
|---|---|---|
| 12 canonical error categories (`VALIDATION_ERROR`, `PROVIDER_UNAVAILABLE`, `PROVIDER_REJECTED`, `STALE_DATA`, `UNSUPPORTED_CAPABILITY`, `ACCOUNT_UNAVAILABLE`, `RISK_BLOCKED`, `MODE_BLOCKED`, `AUTH_ERROR`, `RATE_LIMITED`, `TIMEOUT`, `INTERNAL_ERROR`) | `STALE_DATA`/`RATE_LIMITED`/`TIMEOUT` → `caution`; `VALIDATION_ERROR` → `neutral`; rest → `critical` | Human sentence per category ("The data provider is unavailable", "Risk controls blocked this order"); `category: reason_code` raw string in TechnicalDetails. Unknown category → fail-closed `critical` "Unexpected error" (preserves `errors.ts` behavior) |
| `InstrumentSelectionAction` (10 values) | `OPEN_*` → `live`; `REFERENCE_ONLY` → `neutral`; `UNSUPPORTED_INSTRUMENT` → `caution` | "Open workspace" / "Reference only — no workspace" / "Unsupported instrument" |
| lifecycle actions (`setup, start, stop, restart, open, check_update, apply_update`) | `neutral` (actions, not states) | "Restart platform" etc.; `apply_update` confirm-gated |
| update status `AVAILABLE` | `caution` | "Update available" |
| `LaneSourceKind` (`lane_payload, context_as_of, retrieved_at, unknown`) | `unknown` → `caution`; others `neutral` | L4 provenance labels only |
| explore row free strings (`outcome_status`, `evidence_coverage`, `research_detection`, `freshness`, `mode_label`, `capability_state`, `epistemic_class`) | map recognizable values via above tables; else `neutral` | humanized labels; raw in TechnicalDetails |
| admitted-instrument unavailability ("no admitted replay fixture for {symbol}") | `neutral` | "No replay data for {symbol} in this demo build. Admitted instruments: {list}." |

## 4. Subsystem disagreement

The backend already emits a "contexts disagree" signal; the UI anchors on it instead
of inventing one:

- **Primary anchor:** `WorkspaceEvidenceResponse.coherence_warning`
  (`ui/src/api/schemas.ts:2007`) — backend-computed disagreement across evidence
  contexts.
- **Secondary anchor:** `research_context_execution_authority` (`schemas.ts:2012`) —
  when research context and execution authority diverge.
- **Client-detected disagreement** (presentation only, never new truth):
  `evaluateModeContext` mismatch (UI mode vs backend `/context`); portfolio ledger
  authority vs `/context` authority (audit 03 contradiction #1); frozen vs current
  evidence for one symbol (overview `frozen` vs squeeze lane `?data_mode=current`).

**Representation (binding):**
1. StatusBar shows a `caution` indicator "Sources disagree" (with icon + text) when
   any anchor fires. It never silently picks a winner.
2. Clicking opens a `ContradictionPanel` listing each disagreement as: what each
   side says (humanized), which surface trusts which source, and what the operator
   should do (usually: "execution controls stay locked until aligned" / "check
   Providers in Control").
3. Raw values (`coherence_warning` payload, both authority triples, both data modes)
   in TechnicalDetails inside the panel.
4. Fail-closed rule preserved: when authority sources disagree, the **strictest**
   source gates mutations (today's effective behavior: ticket requires both
   `paperActionsPermitted` and the portfolio account check). The UI must say so in
   words.

## 5. Adapter / selector rules (binding)

1. **Single entry point.** All enum/state rendering goes through
   `resolveSemanticState`. No component re-derives tone with local ok-sets
   (`paperDashboardViewModel.ts:8-11`, `liveDashboardViewModel.ts:108-128`,
   `capabilityPresentation.ts:8-14` get replaced by adapter calls; the sets themselves
   move into the adapter as the domain tables above).
2. **Unknown = neutral + raw.** Unmapped values render `neutral` tone, the raw string
   in a detail surface, and a dev-mode console warning. Never guess a sentence; never
   throw (presentation layer must not fail-closed on *display* — fail-closed applies
   to *mutations*).
3. **No new truth.** The adapter never computes operational state (e.g. it does not
   decide an order is "risky"); it translates backend-emitted state only. Client-side
   thresholds that already exist (lane staleness 5-min, kill-switch ok-sets) are
   documented above and move into the adapter unchanged.
4. **Authority gating stays in guards.** `canUsePaperActions` / `hasPaperAuthority` /
   `evaluateModeContext` remain the gating logic; the adapter only words their output.
   The triple-sourced authority divergence (audit 03 #1) is surfaced via §4, not
   "fixed" in the adapter. The stricter `PaperNowPage` check (`PAPER_ONLY` exactly)
   and the permanently-closed derivative preview gate are flagged in
   [decision-log.md](decision-log.md) — not silently changed.
5. **Pure and tested.** The adapter is a pure TS module with a unit test per mapped
   value + unknown-value tests per domain (mirrors `modeAuthority.test.ts` pattern).
6. **Insertion points.** StatusBar (replaces `ContextBar`/`ModeEnvironmentBar` raw
   renders), `ModeBadge`, `SystemHealth`, `ProviderHealth`, `FreshnessIndicator`,
   `AttentionBanner`, `DegradedState`, order/position rows, lane panels.

## 6. Freshness & confidence presentation standards

**FreshnessIndicator** — one component, three inputs: `asOf` (timestamp),
`cadence` (expected poll/update interval), `override` (backend `freshness_label` /
`data_status` when present — backend word wins).

| Context | Fresh | Lagging | Stale |
|---|---|---|---|
| Live market data (2s poll: order-flow, order-book, market-state) | < 5s | 5–15s | ≥ 15s |
| Live workspace evidence (5s poll) | < 15s | 15s–5m | ≥ 5m (matches existing client threshold, `laneProvenance.ts:90-97`) |
| Provider health (5s poll) | < 15s | 15–60s | ≥ 60s |
| Canary (15s poll) | < 45s | 45s–2m | ≥ 2m |
| Discover (server-driven ~3s) | server `freshness_label` passthrough + tone map | — | — |
| Replay / frozen | no decay — render "as of {human time}" with `replay` tone | — | — |

Display: "updated 2m ago" (relative, tick-refreshed at most 1/s); stale adds the
sentence consequence ("— quotes may be delayed"); raw ISO/epoch in TechnicalDetails.
Never render raw `freshness {ms} ms` or `mark_as_of_ns`.

**ConfidenceIndicator** — bands, not false precision: `Low` / `Medium` / `High`
(+ numeric value in tooltip and TechnicalDetails). Sources: backend confidence
fields only (e.g. squeeze `confidence`, opportunity `ranking_vector` components).
The UI bands (`<0.33` / `<0.66` / `≥0.66` default, overridable per domain); it never
computes confidence from scratch. Missing confidence → render nothing (not "Unknown"
noise) except in L3 evidence grids, where "—" with a tooltip is allowed.

**Evidence strength** on opportunities combines: `ConfidenceIndicator` +
source-agreement count ("3 of 4 sources agree" via `EvidenceStack`) +
`FreshnessIndicator`. All three must be visible in the expanded card; the compact
card shows confidence + freshness only.

## 7. Domain `action` (operator-action availability)

Added with the Control operator-action foundation. This domain translates presentation
availability only. It does not replace domain reason codes.

| Value | Tone | Label |
|---|---|---|
| `AVAILABLE` | `live` | "Available" |
| `BLOCKED` | `critical` | "Blocked" |
| `READ_ONLY` | `neutral` | "Read-only" |
| `UNAVAILABLE` | `neutral` | "Unavailable" |

Unknown values stay on the shared neutral fallback with the raw token preserved.
See [FRONTEND_GUIDE.md](../engineering/FRONTEND_GUIDE.md) for `OperatorActionDescriptor`.

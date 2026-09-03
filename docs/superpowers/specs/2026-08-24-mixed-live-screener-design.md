# Mixed Live Screener Design

**Date:** 2026-08-24

**Status:** Approved

**Primary surface:** `/discover`

## Outcome

Turn the existing Finviz discovery page into a mixed opportunity screener that combines broad, semi-live candidate discovery with the freshest market observations the platform can obtain. Finviz Elite finds and explains the candidate universe. Moomoo is the first live enrichment provider because its quote, trades, and order-book runtime already exists in the platform. IBKR and other feeds can be added later without changing the UI contract or ranking semantics.

The screener is an attention-management tool. Every row remains `INVESTIGATE`; no score, lane, refresh, or promotion can create an order or imply a buy/sell decision.

## Goals

- Replace the single-preset workflow with one deduplicated mixed queue sourced from all existing versioned Finviz screens.
- Preserve understandable opportunity lanes: `MOMENTUM`, `SQUEEZE`, `CATALYST`, and `SWING`.
- Enrich the highest-priority candidates with live Moomoo L1 observations while respecting verified subscription quota.
- Show source, age, and quality explicitly as `LIVE`, `DELAYED`, `SNAPSHOT`, `STALE`, or `UNAVAILABLE`.
- Continue showing useful Finviz snapshot data when Moomoo is disabled, disconnected, unentitled, or awaiting its first event.
- Keep the mixed payload provider-neutral so a later IBKR adapter can participate without rewriting the page.
- Preserve manual `PROMOTE TO LIVE ANALYSIS` and the existing execution-authority boundary.

## Non-goals for this slice

- Broker orders, paper orders, strategy signals, or automatic execution.
- A claim that the queue predicts returns or that its ranking is a calibrated probability.
- Live IBKR market-data integration. The existing IBKR observational tools remain separate until the next adapter milestone.
- Finviz browser scraping or UI credential entry.
- News sentiment, options flow, full Level 2 visualization, or historical ranking research.
- A background daemon that refreshes while the UI and API server are stopped.

## Provider authority

| Concern | Initial authority | Behavior |
| --- | --- | --- |
| Broad-market candidate discovery | Finviz Elite | Runs versioned screens and supplies discovery metrics and reasons. |
| Fast L1 quote enrichment | Moomoo | Supplies admitted quote, volume, bid/ask, provider timestamp, and freshness. |
| Candidate classification/ranking | IMP | Deterministic, inspectable attention ordering; never a trade signal. |
| Instrument identity | IMP canonical symbols | Deduplication occurs only after Finviz-to-canonical normalization. |
| Execution | None | Discovery and enrichment cannot create an order intent or order. |
| Later provider fallback | IBKR/others | Implement the same enrichment contract, then participate by declared quality and freshness. |

Finviz credentials remain in `.private/providers.env` through the existing `FINVIZ_API_KEY` workflow. The UI reports configuration and authentication health but never receives or stores the credential.

## Candidate sources and lane classification

The mixed refresh runs all eight existing screen definitions. A candidate may occupy multiple lanes.

| Finviz screen | Assigned lanes |
| --- | --- |
| `SHORT_SQUEEZE_DISCOVERY` | `SQUEEZE` |
| `UNUSUAL_VOLUME_DISCOVERY` | `MOMENTUM` |
| `MOMENTUM_IGNITION_DISCOVERY` | `MOMENTUM` |
| `GAP_CATALYST_DISCOVERY` | `MOMENTUM`, `CATALYST` |
| `EARNINGS_MOVER_DISCOVERY` | `CATALYST`, `SWING` |
| `ANALYST_EVENT_DISCOVERY` | `CATALYST`, `SWING` |
| `INSIDER_ACTIVITY_DISCOVERY` | `CATALYST`, `SWING` |
| `TECHNICAL_BREAKOUT_DISCOVERY` | `MOMENTUM`, `SWING` |

The aggregator merges candidates by canonical `instrument_id`. It unions lanes, screen matches, matched reasons, and provenance. When multiple captures contain the same metric, the newest available observation wins and every contributing capture remains in provenance.

## Quality and eligibility gates

A row can enter the mixed queue only when it has:

- a valid canonical US-equity symbol;
- at least one contributing screen with usable quality;
- a finite positive discovery price when price is present; and
- a non-empty reason that explains why it matched.

Missing optional metrics do not become zero. They remain `null` and do not contribute to ranking. Live spread is displayed only when both bid and ask are finite and non-crossed. Provider failure retains the last Finviz snapshot and marks unavailable live fields; it never fabricates current values.

The first slice does not add stricter dollar-volume or minimum-price filters because the existing Finviz exports do not yet guarantee all needed liquidity fields across every screen. The payload exposes enough quality and metric detail for those gates to be introduced and research-validated next.

## Attention ranking

The queue uses a deterministic `attention_score` only for ordering operator inspection. The UI labels it **Attention**, never Buy, Sell, Confidence, Probability, or Edge.

Components remain separately visible:

- **setup strength (0–45):** normalized evidence from relative volume, absolute change, short float, and number of distinct matching screens;
- **freshness (0–20):** age of the newest discovery capture plus any admitted live quote;
- **liquidity/marketability (0–20):** available volume and, when live L1 exists, a non-crossed percentage spread;
- **live confirmation (0–15):** a fresh admitted quote and agreement between the live move/volume context and the discovery setup;
- **quality penalties:** stale, degraded, missing-required-field, crossed-market, or unavailable-provider penalties applied explicitly.

Each component is capped; missing inputs contribute nothing rather than a negative invented value. Ties break by newest observation, number of screen matches, then symbol. The response includes `attention_components` and `ranking_reasons` so ordering can be audited.

The implementation must not call this score a recommendation and must retain `candidate_role: INVESTIGATE`.

## Live enrichment and subscription policy

The first `MarketCandidateEnricher` implementation wraps the existing Moomoo `LiveObservationalRuntime`.

- Only `BASIC_QUOTE` is auto-subscribed for the mixed queue. Trades and order book remain available through manual promotion to the workspace, avoiding three quota units per background candidate.
- The target set is the highest-ranked candidates that fit both a configured screener cap and current provider quota. The initial cap is 12 symbols and is configurable with `IMP_DISCOVERY_LIVE_CANDIDATES`.
- Subscriptions use the dedicated consumer id `discover-live-screener` and `BACKGROUND_RESEARCH` priority.
- Refresh reconciliation acquires newly selected symbols and releases symbols no longer in the target set for that consumer only. It never releases another consumer's references.
- Ranking hysteresis keeps an already subscribed candidate when it remains close to the cutoff, reducing subscription churn. The initial rule retains an incumbent whose rank is within three places of the cap.
- When the runtime is absent or unhealthy, the adapter returns explicit provider status and does not create it as a side effect of a read-only poll.

The provider-neutral enrichment record contains:

```json
{
  "provider": "MOOMOO",
  "status": "LIVE",
  "as_of_ns": 0,
  "freshness_ms": 0,
  "last_price": 0.0,
  "bid_price": 0.0,
  "ask_price": 0.0,
  "spread_pct": 0.0,
  "volume": 0.0,
  "quality": "PASS",
  "reason": null
}
```

IBKR can later implement the same contract and declare `DELAYED` when the account's entitlement produces delayed observations. Provider selection is field-aware: the freshest admissible observation wins, while provenance lists every source considered.

## Refresh model

Two cadences avoid expensive provider work on every UI poll:

1. `POST /discover/mixed/refresh` runs a single-flight mixed Finviz refresh, builds the aggregate, and reconciles the live quote target set. Concurrent refresh attempts receive the current result with `refresh_in_progress: true` instead of launching duplicate work.
2. `GET /discover/mixed` is read-only. It rebuilds live fields from current admitted runtime state over the latest mixed discovery snapshot without calling Finviz or changing subscriptions.

In Live mode, the browser:

- requests a mixed refresh immediately;
- polls the read-only endpoint every 3 seconds while the page is visible;
- requests the next discovery refresh after 120 seconds; and
- pauses polling when the document is hidden.

Manual refresh remains available. A refresh can take tens of seconds because the existing Finviz request manager spaces requests; the current queue stays visible with a refreshing indicator. The API server's threaded request model keeps unrelated UI requests responsive.

## Automatic Finviz refresh and credential recovery

Finviz is a periodic request/response discovery source, not a streaming feed. The mixed browser requests a new universe every 120 seconds while visible, and the request manager serializes exports at no more than one request per five seconds. Eight-screen refreshes may therefore span tens of seconds. The previous mixed snapshot remains visible until the new refresh completes.

The Finviz request manager applies bounded exponential backoff after HTTP 429 responses. It honors a valid `Retry-After` header when available and otherwise waits 5, then 10 seconds before returning the final rate-limited response. Rate-limited, login HTML, invalid-auth, and provider-error responses are never cached. Successful classified CSV responses may use their declared cache TTL. Per-screen capture fallback preserves the last valid snapshot when retries are exhausted.

An authentication failure enters one single-flight recovery sequence:

1. Re-read the configured credential sources using the existing precedence rules. If a different non-environment token is present, validate it and atomically adopt it.
2. If no changed token succeeds and stored Finviz login credentials exist, establish a cookie session by first loading the current email-login page, submit the current `email`, `password`, and `remember` fields to `https://finviz.com/login_submit`, then fetch the Elite API explanation page and extract its API key.
3. Validate the recovered key against a small Elite screener export before persisting or swapping it, then retry the original export once.
4. If Finviz requires MFA, CAPTCHA, subscription repair, or repeated recovery fails, stop automated retries for the cooldown window and expose `AUTH_OPERATOR_ACTION_REQUIRED`. Existing snapshots remain available.

The standard-library `urllib` export transport remains the governed provider boundary. Login recovery accepts an injected session factory. The UI/API launcher may register an optional `curl_cffi` session with Chrome impersonation for the login/key-recovery sequence only; when that package is absent, recovery falls back to the standard-library cookie session. No secret, cookie, form body, API key, or credential-bearing URL is logged or returned to the UI.

## API contract

`GET /discover/mixed`

```json
{
  "available": true,
  "mode": "SEMI_LIVE",
  "candidate_role": "INVESTIGATE",
  "execution_authority": "NONE",
  "generated_at": "2026-08-24T00:00:00Z",
  "discovery_as_of": "2026-08-24T00:00:00Z",
  "refresh_in_progress": false,
  "refresh_interval_seconds": 120,
  "poll_interval_seconds": 3,
  "provider_health": [],
  "lane_counts": {},
  "candidates": []
}
```

Each candidate contains:

- canonical identity and `candidate_role`;
- `lanes`, contributing `screen_matches`, and deduplicated reasons;
- Finviz snapshot metrics and capture provenance;
- `attention_score`, its components, ranking reasons, and queue rank;
- a normalized `market` enrichment or an explicit unavailable record;
- `data_status`, `freshness_label`, overall quality, and reason codes.

`POST /discover/mixed/refresh`

- accepts an optional body `{ "screen_ids": [...] }` for tests and operator diagnostics;
- defaults to all versioned screens;
- returns the same envelope plus per-screen outcomes;
- never accepts symbols, order parameters, or credentials.

Existing `/discover/screens`, `/discover/run`, and `/discover/promote-to-live-analysis` routes remain compatible.

## UI design

`/discover` defaults to **Mixed Live** and retains **Single Screen** as a diagnostic mode.

The mixed view contains:

- a mode switch, refresh control, last-discovery time, next-refresh state, candidate count, and provider health summary;
- filter chips for `ALL`, `MOMENTUM`, `SQUEEZE`, `CATALYST`, and `SWING`;
- a compact table on wide screens and readable stacked rows on narrow screens;
- columns for symbol, lane(s), attention, live/snapshot price, change, relative volume, volume, spread, age/status, and why;
- source badges such as `FINVIZ SNAPSHOT` and `MOOMOO LIVE`;
- an expandable evidence section with attention components, all matching screens, provenance, and quality reasons;
- the existing **Open Workspace** action, which is the only path that asks for trades/order-book subscriptions.

Status is conveyed with text in addition to color. A persistent disclosure says: “Candidates are INVESTIGATE, not trade signals.” No row is silently removed merely because live enrichment failed.

## Failure behavior

- **Finviz not configured/auth required:** show the latest saved captures if present, label them `SNAPSHOT` or `STALE`, show the existing local setup command, and keep Live mode degraded rather than blank.
- **Finviz token changed on disk:** automatically reload and validate the changed token before attempting a login-based recovery.
- **Finviz rate limited:** retry with bounded exponential backoff, do not cache the error, and retain the latest successful captures.
- **Finviz login challenged:** stop at `AUTH_OPERATOR_ACTION_REQUIRED`; never attempt to automate MFA or CAPTCHA.
- **One Finviz screen fails:** keep successful screens, return the failed screen's reason, and mark aggregate quality `DEGRADED`.
- **All screens fail with no captures:** return `available: false` and an empty queue with actionable provider status.
- **Moomoo disabled/disconnected/unentitled:** keep Finviz candidates; market records are `UNAVAILABLE` with a reason code.
- **Awaiting first quote:** display `SNAPSHOT` and `AWAITING_FIRST_EVENT`, not a zero price.
- **Stale quote:** retain the value with `STALE`; do not treat it as live confirmation.
- **Quota exhausted:** enrich only admitted target symbols and expose `QUOTA_EXHAUSTED` for remaining candidates.
- **Crossed or invalid market:** omit spread, downgrade quality, and expose a reason.

The latest successful mixed snapshot remains in memory and can always be reconstructed from persisted Finviz captures after restart.

## Safety invariants

- `candidate_role` is always `INVESTIGATE`.
- Finviz execution authority remains `NONE`.
- Mixed refresh and polling never call any order, paper-order, or broker route.
- Auto-subscription is observation-only and limited to `BASIC_QUOTE`.
- Manual promotion reports `order_intent_created: false`, `paper_order_created: false`, and `broker_order_created: false` as it does today.
- Missing, stale, delayed, and unavailable data are explicit and never coerced to current zero values.
- All displayed values identify provider, observation/capture time, freshness, and quality.

## Implementation boundaries

The vertical slice adds:

- discovery mixed-queue domain models, lane mapping, merge, quality gates, deterministic attention ranking, and capture fallback;
- a provider-neutral candidate enrichment interface with a Moomoo implementation;
- mixed read and refresh projections plus two HTTP routes;
- the Mixed Live page mode, polling lifecycle, lane filters, data-status presentation, and responsive styling;
- offline backend and frontend tests plus opt-in provider checks.

It reuses the existing screen library, Finviz request manager/captures, canonical mappings, live runtime/state store, subscription manager, provider diagnostics, and workspace promotion route.

## Test and validation strategy

Implementation follows test-first development.

- Domain tests: lane assignment, canonical deduplication, metric precedence, missing-value behavior, deterministic ranking, tie breaks, and explicit quality penalties.
- Fallback tests: partial/all Finviz failure, latest-capture recovery, stale snapshots, and unavailable Moomoo.
- Live adapter tests: quota-bounded BASIC_QUOTE targets, hysteresis, consumer-isolated release, fresh/stale/crossed quotes, and provider provenance.
- API tests: read-only GET has no Finviz/subscription side effects; refresh is single-flight; payload schema and execution invariants hold.
- UI tests: default mixed mode, lane filters, status labels, refresh/poll lifecycle, hidden-document pause, degraded fallback, and Open Workspace behavior.
- Repository validation after edits uses `tools/validate.py changed`; the final handoff runs the full validator once.
- Real Finviz and Moomoo checks remain opt-in and run only when configured; offline fixtures are the required CI path.

## Acceptance criteria

1. Opening `/discover` presents one deduplicated mixed queue with transparent lanes and reasons.
2. All eight existing Finviz screen families can contribute without duplicate symbol rows.
3. The top quota-safe candidates show fresh Moomoo L1 values within the UI polling cadence when the provider is healthy.
4. Every value clearly distinguishes live, delayed, snapshot, stale, and unavailable data with provenance.
5. A Finviz or Moomoo outage leaves an honest, useful degraded queue rather than an empty or misleading screen.
6. Single-screen diagnostics and manual workspace promotion still work.
7. No refresh, poll, classification, ranking, or subscription path can create an order.
8. Tests and repository validation pass, with live provider checks opt-in.
9. Finviz discovery continues to refresh without operator action across transient 429 responses and a changed stored API key; login/key recovery is attempted automatically when credentials permit it.

## Follow-on work

- Add an IBKR enrichment adapter and entitlement-aware field selection.
- Research stricter liquidity/marketability gates using captured prospective data.
- Calibrate lane-specific ranking components against forward outcomes without turning them into execution signals.
- Add news/catalyst verification and richer trade/order-book confirmation after the L1 slice is stable.

## Implementation outcome

Implemented on `feat/mixed-live-screener` as an isolated vertical slice:

- `GET /discover/mixed` reads the current queue without starting Finviz or changing subscriptions.
- `POST /discover/mixed/refresh` runs the selected Finviz screens through a single-flight refresh, retains per-screen fallback outcomes, and reconciles live candidates once.
- Moomoo is the first live enrichment adapter. It uses the dedicated `discover-live-screener` consumer, requests only `BASIC_QUOTE`, preserves other consumers' references, and reports quota rejection as `QUOTA_EXHAUSTED`.
- `IMP_DISCOVERY_LIVE_CANDIDATES` controls the quote-enrichment cap and defaults to 12.
- `/discover` now defaults to Mixed Live, retains Single Screen, filters by lane, pauses polling while hidden, and labels Finviz snapshots separately from Moomoo market status.
- The response includes `candidate_role: INVESTIGATE` and `execution_authority: NONE`; regression coverage rejects nested order and buy/sell score fields.

Offline verification includes the mixed discovery unittest module, repository changed/domain/full validation, the Vitest UI suite, and a Vite production build. Real Finviz and Moomoo probes remain opt-in and were not required for the offline implementation record.

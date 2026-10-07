# AI Screener: automatic wide coverage and a visible home

Status: **proposed, not approved**. Nothing here is built. Written 2026-10-07 from the first live
prospective session ([readiness report](2026-10-07-oct1-13-pre-rth-readiness.md)).

## Why

Owner feedback during the session:

- 20 names per manual click out of 4,630 is too slow to be useful, and a local model makes it worse.
- The AI Screener lives in a bottom panel that is easy to miss, and nothing tells you a model is running or how far along it is.

What the session showed on top of that:

- The model saw **price and volume only**. News stories were thinned to zero to fit the packet, and Finviz change %, relative volume and RSI are blocked as undated. Both paid runs returned `NO_GROUNDED_CANDIDATES`, and the model said why.
- Candidate quotes stop if the Screener page closes.
- The engine dropdown switches the model for the whole machine immediately, with no confirmation, in the middle of a session.

## What already exists (build on it, do not duplicate it)

| Piece | Where | What it does today |
|-------|-------|--------------------|
| Bounded reduction | `intelligence/inference/candidate_reduction.py` | `MAX_INTAKE = 20`, `MAX_SELECTED = 5`, `MAX_PACKET_BYTES = 96000`; one model call, cached by input hash |
| Packet build | `ui_api/screener_ai.py::_packet` | First 20 rows of the Screener scope, gated evidence, news attached then thinned by `fit_news` |
| **Scheduled loop** | `ui_api/screener_reevaluation.py` | Already re-runs the reduction when the intake changes (at most every 300 s), tracks selected candidates, runs Action Decisions for them (2 per cycle), watches held positions and stops. Lease, heartbeat, dwell, hourly and daily call caps, cycle receipts, no backfill |
| Quote window | `ui_api/screener_projections.py::window` | Page-driven, 32 symbols per client, released 45 s after the page stops asking |
| Held quotes | `live_projections.keep_portfolio_marks_current` | Server-owned subscription for held positions |
| Budget | `anthropic_synthesis.DailyBudget` | 30 requests and 200,000 tokens per UTC day, reserve then settle; no retries |
| UI | `panels/AiScreenerPanel.tsx`, `ReevaluationPanel.tsx`, `ActionDecisionPanel.tsx` | Bottom dock panel; a button label changes to "Running AI Screener…"; reevaluation controls behind a second button |

So "automatic" mostly exists: starting the reevaluation loop already repeats the AI Screener. The gaps are **coverage** (it only ever sees the same first 20 rows), **evidence** (the packet is full of boilerplate), and **visibility**.

## Goals

1. Every name in the universe is considered every cycle by a model-free funnel; the model only sees a shortlist.
2. Shortlist quotes and AI passes run on the server with the Screener page closed.
3. The model gets real evidence: news that survives, dated technicals.
4. At any moment the Screener shows whether a model is working, on what, at which stage, for how long, and what it cost.

## Not in scope

- Automatic Paper submission. Preview and submit stay explicit operator steps.
- Any Live-capital path.
- Changes to the SMA stop, risk limits, fill model or cost policy.
- New data providers.

## Phase 1: visibility (UI first, no methodology change)

Safe to ship before anything else: it changes what you see, not what the model is asked.

### 1a. Run status the server actually knows

The model call is one blocking HTTP request with no streaming, so a percentage bar would be invented. Progress is reported as **stages with elapsed time**:

`SCOPE → EVIDENCE → NEWS → PACKET → BUDGET_RESERVED → MODEL_CALL → VALIDATION → STORED`

- `POST /screener/ai-screener` returns a `run_id` at once and the work continues on the server; `GET /screener/ai-screener/runs/{run_id}` returns stage, per-stage timings, packet size, candidate counts and the final result. The UI polls once a second while a run is active.
- `MODEL_CALL` shows elapsed seconds against the typical latency for that model (the session's Haiku call took 10.8 s) and the request timeout, so "slow" and "stuck" look different.
- A run survives closing the panel or reloading the page: the UI re-attaches to the active run.
- One run at a time per account; a second click joins the run in progress instead of failing.

### 1b. A persistent AI strip on the Main Screener

Always visible under the Screener header, not inside a dock panel:

```
AI  ● Running · model call 7s · claude-haiku-4-5 · 20 candidates      Budget 87k / 200k · ~2 runs left      [Stop]
AI  ○ Idle · last pass 09:58 · 0 of 20 selected · next automatic pass in 2:13                        [Run now] [Open]
```

- States: idle, running (with stage), waiting for budget, blocked (with the reason in plain words), loop stopped.
- Countdown to the next automatic pass and to evidence expiry.
- Budget meter in runs-left terms, not just tokens.
- One click opens the detail view.

### 1c. Results where the rows are

- A badge on each Screener row the model selected (rank), plus a marker for "in the current shortlist".
- An **AI** tab beside Quick Preview in the right rail replaces the bottom panel as the home for results, decisions and reevaluation controls. The bottom-dock entry stays as a shortcut to it.
- "Nothing selected" is shown as short reason chips (no news, technicals blocked, stale quote on LABT) with the model's full text behind a disclosure, instead of one long paragraph.
- Run history: time, engine, state, selected count, tokens, latency; and what was added or removed since the previous run.

### 1d. Engine picker safety

- Changing engine asks for confirmation and says it applies to every panel on this machine.
- Locked while the loop is running.
- Each engine shows whether the current packet fits it. A 4B local model is marked unsuitable for a 35k-token packet instead of being silently selectable.
- Every result and receipt already records its engine; the strip shows it too.

## Phase 2: evidence the model can use

This changes the model's input, so it starts a new evidence series (see Governance).

- **Slim the packet.** About 35 KB of the 96 KB is per-candidate status repeated 20 times (provider clocks, method prose, limitation text). State shared text once per packet and keep a compact per-candidate status. Expected result: stories survive, or more candidates fit per call.
- **Reverse the thinning order.** Thin status detail before stories, not after (the 2026-10-07 fix did the minimum; this does it properly).
- **Dated technicals.** Change %, relative volume and RSI come from Finviz with no observation time, so they are blocked. Where the Moomoo snapshot already carries the inputs with a provider clock (last, previous close, volume), derive change % and volume ratios from it. RSI stays blocked unless computed from our own bars. *Owner decision: this is evidence sourcing, not strategy, but it does change what the model sees.*
- **News for the shortlist only.** Per-instrument Finnhub and NewsAPI refresh is skipped today (`NO_INSTRUMENT_REFRESH_FOR_AI_REDUCTION`) to protect quotas across 20 arbitrary rows. With a stable shortlist a bounded refresh becomes affordable; NewsAPI stays `DELAYED`.

## Phase 3: wide coverage

### 3a. Model-free funnel over the whole universe

- On every universe refresh, score all rows server-side from reference fields already present (volume, relative volume, change, float, price floor, spread where known) and keep a ranked **shortlist**.
- Deterministic, versioned, recorded per cycle with its inputs. It is a coverage filter, not a signal: it decides what gets quotes and model attention, never what gets traded.
- The scoring rule is a named, frozen policy. *Owner decision: which fields and weights.* Default proposal: the operator's saved Screener screen defines the shortlist, so the funnel is "the top N of the screen you chose" rather than a new formula.

### 3b. Server-owned shortlist quotes

- The server subscribes the shortlist itself, like it already does for held positions. The page window keeps working for whatever is on screen.
- OpenD allows 100 subscriptions. Proposed split, to be verified against real slot usage: held positions first, then the page window (32), then specialist panels, and the remainder (about 40) for the shortlist.
- If the shortlist is larger than its allowance it rotates in groups with a minimum dwell, and each group's evidence is only used while current. Nothing is backfilled for the time a symbol was not subscribed.
- The strip shows "shortlist 40 of 4,630 · 38 live".

### 3c. Batched automatic passes

- Extend the existing loop, not a second scheduler: its intake becomes the shortlist instead of the first 20 rows of a page scope.
- Shortlist larger than one packet: batches, then one final pass over the batch winners. Material-change gating already skips the model when nothing moved.
- Budget: a full pass on Haiku was 43,638 tokens. The 200,000-token day allows about four. *Owner decision: the daily budget.* For scale, at Haiku list prices as I recall them that run was about five cents, so a budget ten times larger is a few dollars a day; verify current pricing before choosing. Prompt caching is not used today and would cut the repeated prompt and schema cost.
- Local model: not used for batch passes. Keep it selectable only where the packet fits its context.

## Phase 4: smaller quality-of-life items

- Banner while candidate quotes still depend on the page: "Quotes for these rows stop if this page closes", and a warning when the tab is hidden long enough to stall the universe refresh.
- Paper experiment chip in the Screener header: equity, cash, open positions, with a link to the lifecycle view.
- Desktop notification and optional sound for: candidate selected, decision `ENTER` or `EXIT`, stop breach, loop stopped or lease lost, budget exhausted.
- Errors in plain words with the code underneath (`EVIDENCE_PACKET_BOUND_EXCEEDED` becomes "Too much evidence for one call").
- Evidence-expired results offer a one-click rerun and show what it will cost.
- Keyboard: open the AI tab, run now, jump to the next selected row.
- The narrow panel clips its left edge (visible in the session screenshots); make the layout responsive.
- The start script opens the Screener directly in Paper mode in the default browser.
- Fix found in passing: the Radar investigation screener returns 500 because the secret-leak guard rejects `source_authority_label` values.
- Repair the two browser acceptance scripts (`oct1_09` locator, `oct1_11` browser path).

## What must not change

- Evidence is gated before inference; blocked or stale evidence never reaches the model as current.
- Fail closed: no fabricated decision when evidence is missing.
- Paper preview and submit are explicit; reevaluation never previews, hands off or submits.
- No Live-capital authority anywhere.
- Lease, fencing, dwell and "missed cycles are not backfilled" apply to every new scheduled path.
- SMA stop evaluation continues when the model or evidence is unavailable.

## Governance

Phases 2 and 3 change methodology. Receipts and cycle records carry a methodology version (packet schema, funnel policy id, subscription policy id), and the evaluator never pools runs across versions. The 2026-10-06 and 2026-10-07 sessions stay as their own series.

## Tests and acceptance

| Phase | Proof |
|-------|-------|
| 1 | Stage reporting from a controlled slow engine; re-attach after reload; one run per account; UI tests for every strip state; browser acceptance with a run in progress |
| 2 | Packet-size tests at 20 full live rows with stories surviving; input-hash and cache identity tests; derived technicals carry the provider clock and block when it is missing |
| 3 | Funnel determinism and versioning; subscription allowance never exceeded with held positions and the page window present; rotation dwell; loop tests with the page closed; budget exhaustion fails closed |
| All | Full ladder, complete UI suite, production build, and one premarket operational check before any prospective use |

## Delivery order

1. **Phase 1** (visibility) — independent, no methodology change, immediately useful. Two or three PRs: run status API, strip and AI tab, engine safety.
2. **Phase 2** (evidence) — one PR for the packet, one for dated technicals, one for shortlist news.
3. **Phase 3** (coverage) — funnel, then server-owned subscriptions, then loop intake and batching.
4. **Phase 4** items ride along with the phase they touch; the two bug fixes can go first.

## Decisions needed from the owner

| # | Decision | Recommendation |
|---|----------|----------------|
| 1 | What defines the shortlist | The operator's saved screen, top N by its sort; no new scoring formula |
| 2 | Shortlist size | About 40, bounded by the OpenD allowance after held positions and the page window |
| 3 | Daily model budget | Raise it deliberately once Phase 2 shows the packet is worth sending; keep 200k until then |
| 4 | Derive change % and volume ratios from Moomoo snapshots | Yes |
| 5 | Local model for batch passes | No; hosted model only, local stays for small single-candidate work |
| 6 | Automatic passes start on their own at 09:30 | No; the operator presses Start once per session |

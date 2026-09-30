# Screener S11 — Cross-universe News, Headlines, Sentiment & Analysis

Status: **implemented (S11, 2026-09-28)** — stacked on
[Screener S10](SCREENER_S10_CRYPTO.md).

News is a cross-universe **intelligence layer**, never a universe. The
registry still holds exactly five core universes (`US_EQUITIES`, `US_ETFS`,
`FUTURES`, `BONDS`, `CRYPTO`; see
[SCREENER_UNIVERSE_ARCHITECTURE.md](SCREENER_UNIVERSE_ARCHITECTURE.md)), and
`tests/platform/test_screener_s11.py` pins that no `NEWS` entry exists. S11 adds
three surfaces over the **active** universe:

| Surface | What it is | Request |
|---------|------------|---------|
| Screener **News** view | The last tab in the views tablist; a dense, virtualized story feed scoped by the active universe | `GET /screener/news` |
| **News & Analysis** dock panel (`news`) | Selected-instrument headlines, sentiment, catalysts, attention, post-headline reaction, analysis, AI synthesis, provenance | `GET /screener/news/instrument` |
| Quick Preview **News** | Compact: 3–5 newest stories, sentiment line, latest catalyst, provider states, "Open News & Analysis" | `GET /screener/news/instrument?compact=1` |
| AI synthesis | Explicit operator action only | `POST /screener/news/synthesis` |
| AI engine picker | Operator choice of engine + model (calls no model) | `POST /screener/news/synthesis/engine` |

## Architecture

```
providers (adapters)            canonical news                        derived layers                    read models
------------------------        ---------------------------------      -------------------------------   -------------------
Finviz Elite bulk export  ─┐    normalize_raw_item → NewsArticleEvent   event_taxonomy (categories)       feed (News view)
Public RSS/Atom catalog   ─┤ →  dedupe_events (exact duplicates)    →   instrument_matching (basis)   →   instrument (panel,
NewsAPI (per instrument)  ─┤    story_clusters (syndication groups)     finbert_sentiment (language)       Preview compact)
Finnhub (per instrument)  ─┤                                            attention windows, reaction        synthesis (AI)
SEC EDGAR filings         ─┘                                            brief (deterministic)
```

- Domain: `src/market_platform_foundation/news/` — `event_taxonomy.py`,
  `story_clusters.py`, `instrument_matching.py`, `finbert_sentiment.py`,
  `rss_feeds.py`, `sec_filings_news.py` (plus the existing canonical
  `contracts.py`, `normalize.py`, `dedupe.py`, `timestamps.py`, `providers.py`,
  `catalysts.py`).
- Read models: `ui_api/screener_news.py` (`ScreenerNewsService`).
- AI: `intelligence/inference/screener_synthesis.py` and prompt
  `news.screener_synthesis.v1` (task `NEWS_SCREENER_SYNTHESIS`) in the canonical
  `PromptRegistry`, run through the canonical `InferenceProvider`.
- UI: `ui/src/api/screenerNews.ts` (strict zod schemas),
  `ui/src/components/screener/news/`, `panels/NewsAnalysisPanel.tsx`.
- Routes: `GET /screener/news`, `GET /screener/news/instrument` (`state.read`);
  `POST /screener/news/synthesis` (`state.write` — an operator-initiated call
  with external cost).

There is no parallel news architecture: every item passes through the
canonical `NewsArticleEvent` contract, the canonical normalizer (stable id,
publication-time classification), and canonical dedupe before any S11 layer.

## Three-way harvest

Three sources were audited read-only before implementation: canonical IMP
news/intelligence, the Short Squeeze donor (`projects/short-squeeze-project/
short-squeeze-core`, live code under `apps/research_screener/` and
`collectors/`), and the local, gitignored Claude Code News donor (a Node
macOS daemon; news logic in `news/live/*`). No runtime dependency on either
donor exists; donor trees stay references.

### Canonical IMP inventory (reused)

- `NewsArticleEvent` + `normalize_raw_item` (stable sha256 event id; retrieval
  time never enters identity; `NEWS_IDENTITY_INPUTS_REQUIRED` fail-closed).
- `classify_publication_time`: an unknown/malformed publication time stays
  unknown and flagged; it is never replaced by retrieval time.
- `dedupe_events` (exact duplicates), `CatalystRegistry` keyword entries.
- `FinvizNewsClient` (shared `FinvizRequestManager`, 180 s cache),
  `NewsApiClient` / `FinnhubNewsClient` (`IMP_NEWSAPI_LIVE`, `IMP_FINNHUB_LIVE`
  gates, `NEWSAPI_API_KEY` / `FINNHUB_API_KEY`, `NOT_CONFIGURED` / `LIVE_DISABLED`).
- `sec_edgar` Fair Access `SecTransport`, `fetch_submissions`, `FilingEvent`.
- `intelligence/inference`: `InferenceProvider`, `PromptRegistry`,
  `FixtureInferenceProvider`, `AnthropicInferenceProvider`, input hashing.
- `BackgroundCache` (S8) for off-request provider fetches.

Before S11 the Screener read Finviz directly in the S3 preview (at most three
US Equities headlines); that S3 "Why it may be moving" path is unchanged.

### Donor disposition

| Source | Artifact | Capability | Decision | Target use | Reason |
|--------|----------|------------|----------|------------|--------|
| IMP | `news/contracts.py`, `normalize.py` | Canonical item, stable id, time classification | REUSE | Every S11 item | One contract; missing stays missing |
| IMP | `news/dedupe.py` | Exact-duplicate removal | REUSE | Before clustering | Canonical; clustering is additive |
| IMP | `news/catalysts.py` | Corporate/regulatory keyword entries | ADAPT | `event_taxonomy` corporate/regulatory families | Whole-word patterns; ambiguous single words narrowed |
| IMP | `finviz/news.py` | Bulk news export | REUSE | Universe feed + instrument | Finviz times read as US Eastern (S3 rule), converted to UTC |
| IMP | `news/providers.py` | NewsAPI / Finnhub adapters | REUSE | Instrument-scope providers | Gates and redaction already canonical |
| IMP | `sec_edgar/*` | Submissions, Fair Access transport | REUSE | `sec_filings_news` | Replaces the broken donor SEC RSS |
| IMP | `intelligence/inference/*` | Provider boundary, prompt registry, hashing | REUSE | `screener_synthesis` | No duplicate AI client stack |
| IMP | `market_context/attention.py` | Fixture-sequence attention scores | REFERENCE_ONLY | — | Built for fixture `InformationEvent`s; S11 attention is explicit windowed counts |
| IMP | `market_context/sentiment.py` keyword-v1 | Keyword baseline | REFERENCE_ONLY | — | Squeeze lexicon with substring matching ("moon", "rocket") mislabels news |
| IMP | `market_context/event_clustering.py` | Type/entity/day clusters over fixtures | REFERENCE_ONLY | — | S11 clusters are story-level syndication groups |
| Short Squeeze | `news_live.py` `NewsOrchestrator` | Merge all providers, headline dedupe, newest-first, last-good cache | ADAPT | `ScreenerNewsService` | Per-provider status per fetch, parsed datetimes, injected clocks |
| Short Squeeze | `news_live.py` Finnhub provider | 429 backoff, 403 wording | ADAPT (pattern) | Provider status mapping | Canonical client reused; donor token-leak bug not carried |
| Short Squeeze | `finnhub_live.py` news | Duplicate Finnhub client | REJECT | — | Duplicate |
| Short Squeeze | `news_live.py` NewsAPI provider | Daily quota discipline, Retry-After | ADAPT | 90/day guard (`DAILY_QUOTA_GUARD`) | Free tier is 100/day |
| Short Squeeze | `server.py` provider status | Configured/available flags | REIMPLEMENT_NATIVE | Independent per-provider `state` | Donor had a status-key bug (Finnhub never "connected") |
| Short Squeeze | `session_state.py` news fields | news count, latest headline/time, catalyst UNKNOWN | ADAPT | Coverage/latest fields | Parsed datetimes (donor sorted strings) |
| Short Squeeze | `server.py` `/api/news/feed` | Feed with class counts | ADAPT | News view counts | Frozen-demo fallback **rejected** |
| Short Squeeze | `sentiment_live.py` FinBERT | Lazy local FinBERT, batching, counts, dominant/MIXED, LRU cache | ADAPT | `finbert_sentiment` | Local files only (no silent hub download), full probabilities, one batching layer |
| Short Squeeze | `sentiment_live.py` keyword provider | Keyword sentiment | REJECT | — | Mislabels common terms ("sec", "short") |
| Short Squeeze | `collectors/rss_news.py` | Google News RSS query | REIMPLEMENT_NATIVE | `rss_feeds` | Single query feed, no Atom, unparsed times |
| Short Squeeze | `collectors/sec_rss.py` | SEC Atom via RSS parser | REIMPLEMENT_NATIVE | `sec_filings_news` | Returned 0 items; placeholder User-Agent |
| Short Squeeze | `collectors/registry.py` | Env-ordered collectors | REFERENCE_ONLY | — | FINRA fixture fallback not appropriate |
| Short Squeeze | `static/scanner.*` | Has-news/sentiment filters, news column, feed pills, detail panel | ADAPT | News view / panel patterns | `noopener`, case-safe sentiment |
| Claude Code News | `news/live/sources.mjs` | Official Fed feeds + wire/markets RSS list | ADAPT | `rss_feeds.FEEDS` | Reviewed catalog; Truth Social/Telegram/Reddit rejected; Twitter reference only |
| Claude Code News | `news/live/monitor.mjs` RSS parser | Regex RSS parser, missing `pubDate` → now | REIMPLEMENT_NATIVE | `rss_feeds.parse_feed` | Unknown time stays unknown |
| Claude Code News | `news/live/focus.mjs` KEEP/DROP | Macro keyword tables (Fed, rates, inflation, labor, Treasury/DXY, indices, tariffs, conflict/oil) | REUSE (ported) | `event_taxonomy.MACRO` | Measured, concrete; whole-word |
| Claude Code News | `morning_brief.mjs` tiers | Pre-open / wire / secondary ordering | ADAPT | Synthesis evidence order; Brief | Provenance order, not credibility |
| Claude Code News | `focus.mjs` prompt | Tiered prompt, neutral default, JSON output | ADAPT | `news.screener_synthesis.v1` | Direction/stop outputs removed; grounded refs added |
| Claude Code News | `morning_brief.mjs` Anthropic call | Raw HTTPS client, brace-slice JSON | REJECT | — | Canonical inference provider instead |
| Claude Code News | parse-failure ≠ neutral | Distinct failure state | REUSE (pattern) | `INVALID_OUTPUT` | Malformed AI output is never an empty "current" result |
| Claude Code News | `preflight.mjs` feed staleness | Dead/stale feed detection | ADAPT | Per-feed state + last-good `STALE` | Status, never a block |
| Claude Code News | `shadow_log.mjs` +N-minute snapshots | Post-decision price snapshots | ADAPT | Post-headline price reaction | Labelled temporal association |
| Claude Code News | TradingView CDP news, market scanner | Session-cookie news, cross-asset poller | REFERENCE_ONLY | — | Needs a logged-in browser; unofficial endpoint |
| Claude Code News | launchd, iMessage, broker UI, executor | Scheduling, alerts, trading | REJECT | — | Out of scope; no execution |

## Providers

| Provider | Role in S11 | Scope | Gate / credential | Cache / rate |
|----------|-------------|-------|-------------------|--------------|
| Finviz Elite | Ticker-tagged headlines (latest export window) | Universe + instrument | Finviz Elite key (operator credential manager) | Request manager 180 s; S11 120 s |
| RSS / Atom catalog | Fed releases & speeches, CNBC, MarketWatch, OilPrice, CoinDesk, Cointelegraph, SEC press releases | Universe + instrument | `IMP_NEWS_RSS_LIVE=1`; SEC feed needs `SEC_USER_AGENT` | 300 s per feed; 10 s timeout; 2 MB cap; 60 items/feed |
| NewsAPI | Company/asset-name query (Developer plan: `DELAYED`, development only) | Instrument (Equities, ETFs, Crypto) | `IMP_NEWSAPI_LIVE`, `NEWSAPI_API_KEY` | 900 s per query; 90/day guard (persisted) |
| Finnhub | Company news | Instrument (Equities, ETFs) | `IMP_FINNHUB_LIVE`, `FINNHUB_API_KEY` | 600 s per symbol |
| SEC EDGAR | Recent event filings (8-K, 10-Q/K, S-1/3, 424B, 13D/G, 4, …) as `OFFICIAL_FILING` | Instrument (Equities) | `IMP_EDGAR_LIVE=1`, `SEC_USER_AGENT` | Ticker map 24 h; submissions 600 s; global Fair Access throttle |
| FinBERT (local) | Headline language sentiment (`IMP_DERIVED_FINBERT`) | Feed + instrument | `IMP_FINBERT_MODEL_PATH` or the setup manifest | Background load; LRU 4,096 |
| AI synthesis | Grounded synthesis | Operator action | Operator-picked engine: local model (setup manifest), or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 30 min by input hash |

Free-capability activation (2026-09-30) updated this table; see
[SCREENER_FREE_CAPABILITY_ACTIVATION.md](SCREENER_FREE_CAPABILITY_ACTIVATION.md).

Provider retrieval order is not a credibility ranking; no trust hierarchy is
displayed. Each provider reports its own state — `CURRENT`, `STALE`,
`DELAYED`, `PENDING`, `NOT_CONFIGURED`, `LIVE_DISABLED`, `RATE_LIMITED`, `AUTH_FAILED`,
`ERROR`, `NOT_APPLICABLE` — with a stable reason code; News is never collapsed
into one "available" flag, and `NOT_CONFIGURED` is never rendered as "no news".
Provider fetches run off the request thread (`BackgroundCache`) with a bounded
wait; nothing is fetched per visible row.

## Contracts and time semantics

Stories carry `story_id`, representative `headline`, `summary` (provider
excerpt only, RSS excerpts capped at 280 characters — never article bodies),
`url`, `published_at` + `published_time_quality`, `latest_published_at`,
`first_retrieved_at`, `source_type` (`NEWS` / `OFFICIAL_RELEASE` /
`OFFICIAL_FILING`), per-member `sources` (publisher, provider, `published_at`,
`retrieved_at`, `available_at`, `ingested_at`, URL), `source_count`,
`provider_count`, `categories`, `matches`, `sentiment`, `quality_flags`. The
full contract is in `ui/src/api/screenerNews.ts`.

- Publication, availability, retrieval, and ingestion clocks stay separate.
  An unknown publication time is shown as "time unknown · retrieved HH:MM";
  window membership then uses retrieval time as an explicit age proxy.
- Finviz export `Date` values are US Eastern wall clock
  (`PUBLISHED_TIME_US_EASTERN_WALL_CLOCK`), RSS `pubDate` is RFC 822/ISO with
  offset (a time without a zone is `PUBLICATION_TIME_NO_TIMEZONE` → unknown),
  SEC filings use the EDGAR acceptance time (`SEC_ACCEPTANCE_TIME`).
- Epistemic classes stay separate: **Observed** (headline, publisher, times,
  filings), **Derived** (categories, matches, sentiment, attention,
  post-headline reaction, brief), **AI synthesis** (labelled per block with
  model and time), **Unavailable** (provider/model states), **Insufficient
  evidence** (always states that no causal link is established).

## Dedupe and story clusters

Canonical `dedupe_events` first removes exact duplicates of one provider item
(e.g. the same Finviz item on two polls). `story_clusters.cluster_stories`
then groups independent copies of one story: same canonical URL, same
provider-native id, or normalized headlines (publisher suffixes stripped,
stopwords removed) with token Jaccard ≥ 0.8 within 12 h of the first copy.
Five syndicated copies are **1 story · 5 sources**, with every member source
expandable. Distinct developments ("beats earnings" vs "misses revenue") are
not merged; the same headline on different days is two stories. The cluster id
derives from the earliest member's normalized headline and UTC date, so it is
stable across input order and later copies.

## Cross-universe matching

`instrument_matching.profile_for_row` builds per-universe evidence; every
match carries `basis` and `confidence` (`EXACT` / `CONTEXT` / `AMBIGUOUS`).
Ambiguous evidence alone never makes a story "news for" an instrument.

| Universe | Bases |
|----------|-------|
| US Equities | provider ticker tags, cashtag / exchange-qualified ticker, company entity name (generic single words such as "Target" stay ambiguous), SEC CIK; a bare uppercase ticker is `AMBIGUOUS` |
| ETFs | provider ticker tags, fund name, explicit underlying-theme map for widely held funds (`CONTEXT`) |
| Futures | root → underlying concept (index, energy, metals, rates, FX, grains, livestock, crypto, VIX) plus macro-category context; unmapped roots report `PARTIAL` |
| Bonds | exact CUSIP; otherwise issuer-level Treasury / rates / Fed context — capability `PARTIAL · ISSUER_LEVEL_CONTEXT_ONLY`; never instrument materiality |
| Crypto | asset name (with superstring guards: "Bitcoin Cash" ≠ BTC), pair notation, cashtag, provider tags, venue; bare `SOL` is `AMBIGUOUS` ("SOL Global" never matches Solana) |

In the universe feed, crypto sector-wide and venue context is one match
("Crypto sector" / "Kraken (venue)"), not one per pair. In a pair's panel,
sector context comes only from regulatory or exchange/venue events; generic
crypto-market commentary stays in the universe News view.

## Event categories

`event_taxonomy` derives categories with whole-word patterns: corporate and
regulatory families from the canonical catalyst registry; macro families
(Fed/monetary policy, inflation, labor, growth, Treasuries/rates, dollar/FX,
energy, metals, agriculture/weather, trade policy, geopolitical, broad index)
ported from the Claude Code News tables; crypto families (regulation, ETF
flows, exchange/venue events, protocol/network); SEC filing. Families are
scoped per universe, so an equity "SEC" story is never crypto regulation.

## Sentiment (FinBERT)

`finbert_sentiment.FinbertSentiment` loads a **local** FinBERT directory
(`IMP_FINBERT_MODEL_PATH`) with `local_files_only=True` — nothing is downloaded
— lazily on first use under a lock, never at start-up. Batch size 16, full
positive/neutral/negative probabilities (`top_k=None`), model id and revision
(hash of the model config) on every score, an LRU cache keyed by revision and
text hash. A missing path is `NOT_CONFIGURED`; a missing torch/transformers
runtime or a load failure is `UNAVAILABLE`; an inference failure marks those
items `ERROR`. Empty text is `NOT_SCORED`. No score is ever neutral or negative.

Aggregation is transparent counts over stories (one score per story's
representative headline): positive / neutral / negative, scored / unscored,
the latest scored label, and a dominant label (a tie for most frequent is
`MIXED`). There is no composite score and no weighting. Sentiment describes
headline language; it is never a forecast, and no UI text translates it into
direction. The News view's sentiment filter is enabled when the model is
current and at least one story in the window is scored. With partial scoring
(reason `PARTIAL_SCORING`) an applied filter shows scored stories only and
reports the unscored stories it hid (`filters.sentiment.hidden_unscored`, shown
as "N unscored hidden"); unscored stories are never silently dropped. The feed
also carries `scored`, `unscored`, and per-label `counts`. With no scored story
or a non-current model the filter is disabled with its reason.

The instrument read model adds `sentiment.timeline`: 72 hourly buckets over the
72 h window (oldest first) of story counts by tone (`positive`, `neutral`,
`negative`, `unscored`), keyed by known publication time; stories without one
are excluded and counted in `timeline_untimed`. The Quick Preview and the
News & Analysis panel draw it as a small stacked sparkline (24 h hourly or
72 h in 3 h bins) with text totals and a screen-reader table.

## News view

A dense, virtualized table (Time, Instruments, Headline, Source, Category,
Sentiment, Type; at most three match chips plus "+N"), inside the active
universe. Controls come only from the server: window (1h/4h/24h/72h), sorts
(`newest`, `oldest`, `sources` = most independent sources, `relevance` = match
strength then newest — no opaque ranking), source and category filters with
counts, the sentiment filter as above, instrument filter from a match chip,
and **Brief** mode. Paging is offset/limit (100 per page, max 200) with
prefetch; the footer shows stories · headlines · loaded separately. News state
lives in its own URL parameters (`news`, `nwin`, `nsort`, `nsrc`, `ncat`,
`nsent`, `ninst`, `nbrief`); saved screens and the existing URL contract are
unchanged, and no headline, AI output, or secret is persisted.

Read state is per viewer and kept only in this browser's `localStorage`
(`imp.screener.news.lastSeen.<universe>`, `imp.screener.news.read.<universe>`,
at most 500 opened story ids); storage failures degrade to a first visit.
Stories whose first publication time is after the last view are marked
**New** for the visit; the retrieval time is never used, because it falls back
to the poll time. Leaving News records the feed's `generated_at` as the new
mark; the footer offers **Mark all read**. The News tab shows "N new" from
`GET /screener/news?…&since=<last view>` (`new_count`: window stories published
after `since`, before filters; an invalid `since` is a 400). Keyboard: `j`/`k`
move the active story (`aria-activedescendant`), `o` opens it in a new tab,
`Enter` expands its sources; keys inside row controls and modified keys are
left alone.

## News & Analysis panel

Header (instrument, 72 h window, story count, providers current), a partial-
coverage notice naming every non-current provider, and sections: Latest
headlines (chronological, cluster sources expandable), Sentiment, Catalysts /
Events, Attention, Post-headline price reaction, Analysis (Observed / Derived /
Insufficient evidence), AI synthesis, Provenance (per-provider state, clock,
item count, scope; matching capability, bases, and terms). It fetches only the
settled selection (250 ms settle) while visible, refreshes every 60 s, and
discards any payload whose instrument or universe differs from the settled
selection. One panel instance; not a live-subscription panel.

## Quick Preview

Equities, ETFs, and Futures previews get a **News** tab; Crypto and Bond
previews a collapsed **News** section. Nothing is fetched until the tab is
selected or the section expanded, and only for the settled selection
(`compact=1`: ≤ 5 stories, no reaction). "Open News & Analysis" hands off to
the panel.

## Attention and post-headline reaction

Attention (DERIVED) is headline and story counts over trailing 15m/1h/4h/24h
windows with the preceding equal window as prior (unknown when the prior
window exceeds the 72 h coverage), plus independent sources in 24 h. A provider
outage lowers coverage and is reported as `PARTIAL`; it never reads as zero
attention.

Post-headline price reaction is implemented where reliable current bars exist
(US Equities, ETFs, Crypto): the reference is the close of the last completed
5-minute bar ending at or before publication (within 10 minutes), then the
close at +5m, +15m, +1h (`PENDING` until that bar exists). Futures and Bonds
report `NOT_SUPPORTED`. Every surface labels it a temporal association, never
evidence that a story caused a move.

## Brief

`view=brief` returns a deterministic brief (DERIVED): stories grouped by
category with story, headline, and source counts, latest time, uncategorized
count, missing providers, and a coverage note ("Sparse coverage: …" when there
are fewer than five stories or fewer than two current providers). No model, no
narrative beyond the grouped headlines. An AI universe synthesis is available
through the same synthesis endpoint (`scope=UNIVERSE`).

## AI synthesis

`ScreenerSynthesizer` renders `news.screener_synthesis.v1` (tiered evidence:
official items, then multi-source stories, then single-source) through the
canonical provider and validates the structured result: `summary`,
`observed_facts[]`, `derived_context[]`, `uncertainties[]`,
`conflicting_evidence[]`, `potential_market_relevance[]`, each list item with
`refs` that must name story ids from the packet. Output with unsupported
certainty (upper-case BUY/SELL, "investors should buy", "guaranteed",
"will rally/crash/…") outside quoted attribution is rejected
(`INVALID_OUTPUT · UNSUPPORTED_CERTAINTY`), as is malformed or ungrounded
output. Results carry provider, model, prompt id/version, input hash, cache
state, story ids, and coverage (stories, sources, window, missing providers),
and are cached 30 minutes by input hash (stories + prompt + model); changed
stories produce a new hash and a new call. No provider → `NOT_CONFIGURED`
without a call; no stories → `INSUFFICIENT_EVIDENCE`. The UI shows no Generate
button unless AI is available, and discards a result that arrives after the
selection changed.

### Engine picker

Beside the Generate button, an **AI engine** dropdown picks the engine and model:
the free local model, Anthropic Claude, OpenAI, or Google Gemini, one option per
catalog model (`intelligence/inference/synthesis_engines.py`). An engine without
its key (or a local model that isn't installed) is listed but disabled, with the
reason (for example "needs OPENAI_API_KEY"). The dropdown shows in the not-configured
state too, so the operator can always switch to an engine that works.

- `POST /screener/news/synthesis/engine {engine, model}` (`state.write`) saves the
  choice to `<IMP cache>/settings/synthesis-engine.json` and rebuilds the provider
  on the next request (no restart). Only catalog engines and models are accepted
  (`SYNTHESIS_ENGINE_INVALID` otherwise). It never calls a model.
- Precedence: saved choice → `IMP_SYNTHESIS_PROVIDER` → automatic (Anthropic when
  its key is set, else local). A chosen paid engine without its key is
  `NOT_CONFIGURED · <KEY>_NOT_SET`; it is never silently replaced by another vendor.
- Every AI status (`ai` in instrument news and the synthesis preview) carries
  `engine` (`auto` until one is picked), `engine_model`, `engine_source`
  (`OPERATOR` / `ENVIRONMENT` / `AUTOMATIC`), and `engines[]` (`id`, `label`,
  `runtime`, `models`, `default_model`, `state`, `reason`).
- All paid engines share one hard daily budget (`quota/anthropic-synthesis.json`),
  so switching vendors never resets or multiplies the cap.

## Real acceptance (2026-09-28, 17:55–18:20 UTC)

Run against the live providers configured on the operator workstation:
Finviz Elite (operator credential), public RSS (`IMP_NEWS_RSS_LIVE=1`),
Treasury, Kraken, and Moomoo OpenD for catalogs and bars. NewsAPI, Finnhub,
SEC EDGAR (`SEC_USER_AGENT` not set), FinBERT (no local model; torch/
transformers not installed), and Anthropic were **not configured**, and each
was reported as such.

RSS catalog: 9 of 10 feeds `CURRENT` (Fed press/monetary/speeches, CNBC ×2,
MarketWatch, OilPrice, CoinDesk, Cointelegraph); `sec_press` `NOT_CONFIGURED`.

| Universe (24h feed) | Stories / headlines | Cold / warm | Notes |
|---------------------|---------------------|-------------|-------|
| US Equities | 93 / 94 | 6.3 s / 0.08 s | Finviz ticker tags; one 2-source cluster |
| ETFs | 21 / 21 | 7.7 s / 0.19 s | provider tags (e.g. SOXX) and theme context (SPY/IVV/DIA, TLT/IEF) |
| Futures | 28 / 28 | 3.8 s / 0.52 s | energy 13; ES/CL/HO underlying and macro context |
| Bonds | 6 / 6 | 5.5 s / 0.07 s | Treasury issuer/rates context only |
| Crypto | 34 / 34 | 5.7 s / 3.2 s (0.03 s after the match memo below) | exchange 6, regulation 2; sector matches collapsed |

| Instrument (72h panel) | Stories | State | Reaction |
|------------------------|---------|-------|----------|
| AAPL | 5 (5 sources) | PARTIAL (NewsAPI/Finnhub/SEC disabled) | 4 headlines measured, e.g. −0.18% at +15m, `+1h` pending |
| SPY | 3 | PARTIAL | +5m −0.01% … +1h −0.34% on an earlier story |
| CLX26 (crude) | 15 | CURRENT | `NOT_SUPPORTED` (no reliable futures bar history) |
| 91282CRF0 (10-year) | 8 | CURRENT · capability `ISSUER_LEVEL_CONTEXT_ONLY` | `NOT_SUPPORTED` |
| BTC/USD | 31 | PARTIAL (NewsAPI disabled) | +0.72% at +5m after a stablecoin/Coinbase story |

Sentiment: FinBERT `NOT_CONFIGURED · IMP_FINBERT_MODEL_PATH_NOT_SET` on every
surface; counts 0/0/0 with no dominant label; the feed's sentiment filter is
disabled with that reason. AI: `NOT_CONFIGURED · ANTHROPIC_API_KEY_NOT_SET`;
the synthesis request returned that state in 0.02 s without a model call.
Sentiment and synthesis behavior with a model is covered offline (injected
loader and inference provider).

Provider requests for the whole acceptance run: Finviz 1, RSS jobs 5 (one per
universe, 10 feeds), per-instrument jobs NewsAPI 3 / Finnhub 2 / SEC 1 (all
short-circuited by their gates without network), no per-row requests.

## Visual acceptance

Checked in the in-app browser against a local API (live providers above) and
Vite: 1920×1080 (US Equities News view populated; AAPL News & Analysis panel
with every section; Quick Preview News tab), 2560×1440 (Crypto News view in
Brief mode), ~1100×800 (Crypto preview News section with the panel; Futures
News view; error state with Retry after stopping the API). States seen live:
populated feed, long headlines (ellipsis + title), a multi-source cluster,
partial provider coverage, sentiment not configured, AI not configured, source
timestamps (ET for US universes, UTC for Crypto), loading, and error.

Defects found and fixed during acceptance, each with a regression test:

- crypto sector/venue context repeated for every pair (≈600 matches per story)
  — collapsed to one sector match; pair panels take sector context only from
  regulatory/exchange events;
- crypto ETF-flow category attached a Bitcoin ETF story to every pair — ETF
  flows are asset-specific and match by name only;
- rows grew to two or more lines from a repeated "model not configured" and
  up to seven ticker chips — quiet cell (screen-reader text + title) and three
  chips plus "+N";
- Crypto feed warm latency of 3.2 s — universe matches memoized per event;
- the ~1100 px layout wrapped the Sentiment cell onto a second grid line;
- double punctuation after method/basis strings.

## Performance

- Universe feed cold 3.8–7.7 s (catalog index + provider fetch), warm
  0.07–0.5 s; instrument panel cold 0.04–0.6 s, warm ≤ 0.2 s; compact ≤ 0.05 s.
- Crypto warm was 3.2 s at first acceptance (every listed base asset evaluated
  per story on every request). Universe matches are now memoized per event on
  the cached universe index; re-measured live: cold 3.9 s, warm 0.03 s.
- Universe catalog indexes are cached 10 minutes; provider results by TTL
  above; FinBERT scores by revision + text hash; AI by input hash.
- The UI requests news only for an open News view, a visible panel, or an open
  Preview News tab/section, for the settled selection — never per row.
- Bundle: initial JS 201.41 KiB gzip (budget 203 KiB, unchanged by S11);
  `NewsView` 3.74 KiB and `NewsAnalysisPanel` 4.04 KiB gzip lazy chunks;
  ScreenerDock chunk 460 KiB raw (limit 500 KiB).
- FinBERT batch latency and AI latency could not be measured: neither is
  configured on this workstation.

## Tests

- `tests/news/test_s11_news_domain.py` (34): contract/time semantics,
  dedupe and clusters, taxonomy, matching across all five universes and
  collisions, FinBERT (lazy, batch, probabilities, identity, failures,
  no-data ≠ neutral), RSS/Atom (times, malformed, oversized, gates, cache,
  stale), SEC filings, NewsAPI/Finnhub adapters (normal, bad timestamp, 429,
  auth missing, malformed, empty, failure).
- `tests/platform/test_screener_s11.py` (28): no sixth universe, `news` panel
  in every universe, route policies, feeds for all universes, provider health,
  not-configured ≠ no news, partial state, window/sort/filters/paging,
  sentiment-filter gating, brief, instrument panel, attention, reaction,
  compact preview, per-symbol caching, universe match memo, synthesis (not configured, grounded
  result, cache hit and invalidation, malformed/ungrounded/unsupported output,
  provider failure, insufficient evidence), certainty guard, NewsAPI quota.
- `ui/src/components/screener/news/News.test.tsx` (25): News view, panel, and
  Preview behaviors listed in the S11 brief, plus the five-universe selector.
- Earlier panel-tuple contracts (S5 Futures, S9 Bonds, S10 Crypto) updated to
  include `news`.

## Known limitations

- Finviz's export is its latest-headlines window (100 items at acceptance);
  older ticker news within 72 h depends on NewsAPI/Finnhub being configured.
- Sentiment and AI synthesis were not exercised live: no local FinBERT model or
  Anthropic credential is configured on this workstation. *Unchanged in
  [final closure](SCREENER_FINAL_CLOSURE.md); each reports its not-configured reason.*
- SEC filings and the SEC press-release feed need `SEC_USER_AGENT` and
  `IMP_EDGAR_LIVE=1`; they were not configured. *Superseded by [final closure](SCREENER_FINAL_CLOSURE.md):
  both were exercised live (SEC press feed and NVDA filings `CURRENT`).*
- Matching is keyword/identity based: a company name or asset name appearing
  in unrelated context can still match (`EXACT_ENTITY`), and ETF/futures theme
  maps cover widely held funds and mapped roots only.
- Futures and Bonds have no post-headline reaction (no reliable bar history
  in those universes).
- Provider state is held in process memory; a restart re-fetches.

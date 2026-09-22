# Canonical News/Event Foundation

**Status:** Authoritative (professor-directed post-G15 increment)  
**Scope:** Deterministic ingestion, provenance, filtering, and event-time replay — **no AI, no broker execution**

## Purpose

IMP gathers and curates market-catalyst news deterministically before any AI or strategy layer runs. This foundation answers:

- What item was observed, from where, when published, when retrieved?
- Which instrument(s) does it relate to?
- Has it been seen, is it recent enough, is the source trusted, does it match a catalyst?
- Can the exact decision-time input set be replayed without look-ahead?

Donor audit reference: [CCN_FORENSIC_AUDIT_2026-09-09.md](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md)

## Architecture convergence

IMP already had read-only `news/aggregator.py` (Finviz + NewsAPI + Finnhub) with partial dedupe. This increment **extends** that package rather than introducing a parallel `ArticleEvent` tree:

| Existing | Extended by |
|----------|-------------|
| `news/providers.py` raw normalization | `news/normalize.py` → `NewsArticleEvent` |
| `aggregator.py` URL/headline dedupe | `news/dedupe.py` deterministic identity |
| `NEWS_SOURCES.md` provider config | `news/sources.py` trust catalog |
| Provider envelope time semantics | `news/timestamps.py` publication vs retrieval |
| — | `news/catalysts.py`, `news/filters/`, `news/replay.py`, `news/service.py` |

## Canonical event contract

`NewsArticleEvent` (`news/contracts.py`) is the normalized authority.

| Field | Semantics |
|-------|-----------|
| `event_id` | Deterministic deduplication identity |
| `provider_id` / `provider_native_id` | Provider identity |
| `source_id` | Canonical source-catalog ID |
| `published_time` | Best-known source publication time (may be empty) |
| `published_time_quality` | `KNOWN`, `INFERRED_LOW_CONFIDENCE`, or `UNKNOWN` |
| `retrieved_time` | When IMP observed/received the item |
| `instrument_linkages` | Canonical instrument associations (multi-asset) |
| `quality_flags` | Timestamp/provenance issues **and** provider-linkage evidence-quality warnings |

**Invariant:** `published_time` and `retrieved_time` are never conflated. Missing publication time is `UNKNOWN`, not silently replaced by retrieval time.

### Provider linkage quality (heuristic suspicion, not rewrite)

Module: `news/provider_linkage_quality.py`, hooked from `news/normalize.py`.

When a provider supplies `PROVIDER_SYMBOL` linkages, IMP **preserves** those
tickers (`provider_symbol`, `instrument_id`, `linkage_method`) and may only:

- adjust `InstrumentLinkage.confidence` (`EXPLICIT` /
  `PROVIDER_UNCORROBORATED` / `UNKNOWN`)
- append operator-visible `quality_flags` such as
  `PROVIDER_LINKAGE_TICKER_NOT_IN_TEXT`,
  `PROVIDER_LINKAGE_ALTERNATE_ENTITY_PROMINENT`,
  `PROVIDER_LINKAGE_SOURCE_URL_MISSING`,
  `PROVIDER_LINKAGE_MULTIPLE_CONTRADICTORY`,
  `PROVIDER_LINKAGE_LOW_CONTEXTUAL_CONFIDENCE`

These flags mean **uncorroborated / suspicious association evidence**. They do
**not** declare the provider false, invent a better ticker, drop the event, or
change LIVE_OBSERVED vs HISTORICAL_RECONSTRUCTED gates. Missing URL is a quality
signal only. Empty/unassessable text keeps confidence `UNKNOWN`.

Company-name corroboration is derived from **headline/summary surface forms**
(CamelCase compounds and Title Case words letter-aligned to the provider
symbol). Ordinary English tokens are never treated as rival tickers.
`PROVIDER_LINKAGE_ALTERNATE_ENTITY_PROMINENT` requires an inconsistent CamelCase
company-like span; prefer an absent flag over a false alternate-entity
escalation. Optional raw `company_name` fields are supplemental only —
Finviz production rows need not supply them.

## Observability / availability rule

For IMP observation replay at decision time `T`:

```
observable_time = retrieved_time
observable_time <= T  →  event may enter the pipeline
```

Publication time is used for recency age and event studies, but an item published before `T` yet retrieved after `T` is **not** available in IMP's knowledge state at `T`.

## Filter chain (deterministic, no AI)

Order:

1. **Observability** — `retrieved_time <= as_of`
2. **Deduplication** — provider-native ID, URL, headline fingerprint
3. **Recency** — policy-driven max age (default 72h via `IMP_NEWS_RECENCY_MAX_AGE_SECONDS`)
4. **Source policy** — catalog trust + enabled set
5. **Catalyst keywords** — governed registry match

Each stage emits `FilterDecision` with `reason_code`, `stage`, and matched catalyst IDs.

### Poll rejection observability

Prospective Finviz ingress attaches a privacy-safe `stats.rejection_summary` per
poll/tick (`news/poll_evidence.py`). It records **counts and reason buckets
only** — never raw provider payloads. Undetermined reasons use `UNKNOWN`.
Stages that are not part of the current hop (for example EventV1 persist /
Opportunity mint on hop 1) are marked `UNAVAILABLE` rather than invented.

Existing hop-1 semantics are preserved:

- `ingested_events` — fetched/normalized rows before qualification gates
- `accepted_pipeline_events` — survived NewsPipeline acceptance, catalyst/filter,
  symbol presence, and configured universe membership
- A zero-opportunity tick remains valid; diagnostics do not loosen gates

Bounded campaign poll-evidence retention (digests + dispositions, opt-in via
`IMP_CAMPAIGN_POLL_EVIDENCE_*`) is documented under Configuration below.
Provider-linkage contradiction heuristics are owned by another lane; this
module only exposes the no-op `PROVIDER_LINKAGE_QUALITY_HOOK` extension point.

## Source trust catalog

`SourceTrustCatalog` distinguishes:

- `KNOWN` — named but not configured
- `CONFIGURED` — policy entry (professor-named wires)
- `OPERATIONAL` — wired provider (Finviz, NewsAPI, fixture)

Professor-named sources (PR Newswire, Reuters, FDA, etc.) are seeded as `CONFIGURED`, not operational.

## Catalyst registry

`CatalystRegistry` holds governed keyword sets by category (corporate, regulatory, macro/futures). Not a scattered hard-coded list.

## Replay

`NewsReplayHarness` accepts fixture events + explicit `as_of` ISO timestamp. Repeated replays produce identical accepted sets and stats. See `tests/fixtures/news/canonical_replay_pack.json`.

## Provider extension point

Implement `normalize_raw_item()` output or `FixtureNewsProvider` pattern. Live NewsAPI/Finnhub remain gated (`IMP_NEWSAPI_LIVE`, `IMP_FINNHUB_LIVE`). No scraping, no paid feeds in this increment.

## Downstream boundaries

| Layer | Status |
|-------|--------|
| `NewsIntelligenceService` | Read-only filtered query — **implemented** |
| AI analysis (Claude, etc.) | **Implemented** — see [NEWS_AI_INTELLIGENCE.md](NEWS_AI_INTELLIGENCE.md) |
| Paper strategy signals | **Not implemented** |
| Broker execution | **Not implemented** — unchanged |

## Donor adaptation traceability

| Donor concept | Audit class | IMP implementation |
|---------------|-------------|-------------------|
| 8h buffer / focusFilter / source tiering | ADAPT | Configurable recency + `SourceTrustCatalog` + catalyst registry |
| `publishedAt` only | ADAPT | `published_time` + `retrieved_time` + quality enum |
| shadow/reconstruct | ADAPT | `NewsReplayHarness` + fixture pack |
| `verify_config.mjs` | ADAPT | `verify_news_config()` |

## Limitations (this increment)

- No live PR Newswire / Benzinga / Dow Jones integrations
- Persistence is in-memory / fixture-backed; repository abstraction ready for later storage
- Existing `NewsAggregator` live path unchanged; canonical pipeline is additive
- INT-012 **PARTIALLY_INTEGRATED** — deterministic foundation + AI intelligence concepts adapted; donor executor not integrated

## Configuration

```text
IMP_NEWS_RECENCY_MAX_AGE_SECONDS=259200   # optional, default 72h
IMP_NEWS_RECENCY_FUTURE_TOLERANCE_SECONDS=300
IMP_NEWSAPI_LIVE=1
IMP_FINNHUB_LIVE=1

# Opt-in bounded poll evidence (digests/dispositions only; never raw payloads)
IMP_CAMPAIGN_POLL_EVIDENCE_RETENTION=1
IMP_CAMPAIGN_POLL_EVIDENCE_DIR=/path/to/non-campaign/evidence-root
IMP_CAMPAIGN_POLL_EVIDENCE_MAX_ITEMS=128
IMP_CAMPAIGN_POLL_EVIDENCE_MAX_POLLS=48
IMP_CAMPAIGN_POLL_EVIDENCE_HEADLINE_CHARS=80
```

Retention refuses known `rth-campaign-*` roots even if misconfigured. Missing
retention config is a no-op (`enabled=false`).

Verify: `verify_news_config()` from `market_platform_foundation.news.config`.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests/news -q
```

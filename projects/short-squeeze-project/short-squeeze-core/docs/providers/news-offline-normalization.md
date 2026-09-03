# News Offline Normalization

Phase 1G accepts strict local `NEWS_ITEM_V1` records and emits immutable canonical `NEWS_ITEM` observations. The adapter has no provider client, feed reader, network access, authentication, article fetcher, redirect resolver, or sentiment model.

## Supported input

`NewsRecord` is frozen and rejects unknown fields. It accepts the provider-neutral contract plus only these documented aliases:

- Finviz-shaped: `Title`, `Date`, `Url`, `Ticker`.
- Yahoo-shaped: `content.title`, `content.summary`, `content.pubDate`, `content.canonicalUrl.url`, and `content.clickThroughUrl.url`.
- NewsAPI-shaped: `title`, `description`, `source.name`, `author`, `url`, and `publishedAt`.

Symbols must be explicitly supplied. Headline or company-name text is never used to infer an association. Missing and explicitly empty associations are valid normalized records, but neither is eligible for a symbol-specific evidence bundle.

## Canonical mapping and provenance

The existing `NewsItemPayload` remains unchanged. It carries headline, provider-supplied summary, sanitized URL, publisher, original publication time, and explicit associated symbols. Author, update time, language, content type, lifecycle status, provider availability, capture time, provider identity, URL identity, and revision details remain structured provenance.

Provider availability is `source_timestamp` when supplied; otherwise the adapter uses the defensible publication boundary. `received_timestamp` is the immutable `AdapterContext.ingested_at`, and `effective_timestamp` is their maximum. Date-only input requires `STRICT`, `CONSERVATIVE_END_OF_DAY`, or `UNCERTAIN_PLACEHOLDER` explicitly.

## URL and lifecycle rules

URL normalization is local and uses policy `news-url-v1`: only HTTP/HTTPS, no credentials, a valid host, no fragment, and removal of only the documented tracking keys (`utm_*`, `gclid`, `fbclid`, `mc_cid`, `mc_eid`). Article-identifying query parameters are retained. No URL is fetched.

Exact duplicates are emitted once with diagnostics. Same provider ID with changed content remains conflicted. Updates, corrections, withdrawals, and deletions remain separate observations and link only through provider IDs, canonical URLs, or provider-supplied relations. Equal canonical URLs across providers produce syndication relationships without merging observations.

## Fixtures and command

All 35 cases under `tests/fixtures/providers/news` are `SANITIZED_REPRESENTATIVE_SAMPLE` or `SYNTHETIC_EDGE_CASE`. Archive review found no defensible recorded provider response. In particular, archived `data/news_snapshot.json` is not an objective fixture because it lacks provider, availability, receipt, and reliable publication identity.

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider news --input tests\fixtures\providers\news\representative_cases.json --context tests\fixtures\providers\news\context.json --case news-complete-v1
```


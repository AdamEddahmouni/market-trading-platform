# OCT1-05 â€” News and sentiment evidence integration

Classification: `SOFTWARE_CONTROLLED` implementation acceptance. Runtime probes below are separate operational evidence; no empirical prediction, causal, calibration or execution authority.

## Repository and integration boundary

Canonical monorepo `AdamEddahmouni/market-trading-platform`, IMP at `projects/integrated-market-platform/`. Source base `1e9a3c0c6fe5f474a43bcba10f0763c19951a30b` (OCT1-04, PR #460). Branch `codex/oct1-05-news-evidence-integration`; isolated worktree `.worktrees/oct1-05-news-evidence`. The primary dirty checkout and leftover nested clone were preserved. Integration SHA, required checks and remote-main verification belong to the OCT1-05 PR and existing Notion task; Done requires verified integration.

## Reuse audit

S11 remains the News authority: `NewsArticleEvent`, `normalize_raw_item`, canonical dedupe, `cluster_stories`, story identity, taxonomy, `profile_for_row` / `match_profile`, provider status, Finviz bulk receipts, reviewed RSS feeds, NewsAPI/Finnhub/SEC instrument caches and `BackgroundCache`. No new provider, news store, taxonomy or independent sentiment scorer was introduced. The existing News & Analysis panel remains the drilldown. OCT1-04 retains its intake, output schema, engine picker, shared hosted budget, reducer and evidence IDs. OCT1-03 remains the eligibility authority.

New `screener_news_evidence.py` is a bounded projection of those receipts. Preview reads cache only and never loads or runs FinBERT. Explicit Run refreshes shared Finviz and applicable RSS once, then reads instrument receipts without acquisition. Existing specialist flow is read only when already initialized; no subscription is acquired.

## Evidence contract and clocks

At most 20 candidates, three clustered stories per candidate and 60 unique headline scores before deterministic global thinning. The existing 96,000-byte packet ceiling and five selected-candidate ceiling remain. Exact matches precede context matches, then newest publication and stable story ID. Ambiguous-only, unrelated, future-available/retrieved/ingested and expired stories are excluded. Stories use the explicit `4h` publication relevance window; unknown publication uses an explicitly weak retrieval proxy. No clock is replaced by the synthesis cutoff.

Each NEWS fact carries story ID, bounded headline, source/publisher, source/provider counts, up to three source records and relevance matches/categories, component publication/availability/retrieval/ingestion clocks, omitted source count, membership hash, match confidence/basis, provider coverage, sentiment and OCT1-03 status. Evidence IDs bind identity, material facts, source and expiry. Counts describe syndication, not independent confirmation or credibility. NEWS/SENTIMENT are reference context, never a current price or flow observation.

Expired provider receipts are blocked; a delayed provider stays delayed. Reference weakness propagates to sentiment and prevents strong alignment. The aggregate uses only admitted stories. Packet thinning rebuilds aggregates, IDs, alignments, missing capabilities and candidate sufficiency. Removed stories cannot provide support. Whole-packet identity excludes display evaluation clocks but includes all material story, model, label, membership, comparator and expiry changes.

## Sentiment and comparison semantics

Canonical `ProsusAI/finbert`, `news/finbert-sentiment/1.0.0`, basis `IMP_DERIVED_FINBERT`. Story scores preserve actual revision and positive/neutral/negative probabilities. Canonical aggregation counts each clustered story once by top label; ties yield MIXED. Unscored, loading, unavailable and failed scores never become neutral. This measures headline language; it does not forecast returns or constitute a trading signal.

`headline-language-vs-observed-direction/1.0.0` compares a strong admitted aggregate separately with one current strong `change_pct` and one current strong `net_signed_volume`. Native flow must have complete exchange-native classification, no inferred/unknown trades, a finite signed-volume value and an untruncated observed window ending before the cutoff and starting within four hours. Missing, stale or unsuitable comparators yield UNKNOWN.

| Result | Meaning |
|---|---|
| CONFIRMING | Positive/negative language and nonzero observed direction agree |
| CONFLICTING | Positive/negative language and nonzero observed direction oppose |
| MIXED | Admitted language aggregate ties, with an admissible comparator |
| CONTEXT_ONLY | Neutral language or zero observed direction |
| UNKNOWN | Missing, weak, unscored or inadmissible language/comparator |

Every comparison includes NEWS and SENTIMENT refs, comparator ref, observed direction, method, cutoff and an explicit four-hour reference-versus-observation-window limitation. It asserts neither causality nor trading confirmation. Negative language plus positive observed price is the required controlled CONFLICTING proof, with model revision/probabilities and resolvable refs.

Reproducible controlled Apple proof at `2026-09-28T14:00:00Z`: negative FinBERT fixture `rev001` versus `change_pct=+1.2` and native `net_signed_volume=+42` (three native trades, zero inferred/unknown, one-minute untruncated window) yields two CONFLICTING receipts. NEWS `EV:ab5cec8d5dc0ce1d10d7b4994b1eef67`, SENTIMENT `EV:bb026d7d504e6729f3f1fe0882ca907e`, price comparator `EV:880c0ad81088f951cc8fb74e849bc603`, flow comparator `EV:5ee51b42b6439c5975acefdd32582769`. All resolve to the controlled candidate; this is software evidence, not real market flow.

## AI and operator behavior

Versioned prompt `screener.ai_candidate_reduction.v2` treats headlines as untrusted data, forbids browsing/tool use or invented news and requires conflict disclosure. Parser rejects unknown/unrelated refs, news prose without NEWS refs, sentiment prose without SENTIMENT refs, and a selected deterministic conflict whose sentiment refs are omitted from conflicting evidence or reused as support. All selected candidates display their deterministic News and pairwise comparisons regardless of AI prose.

The UI exposes cached coverage before Run, human-readable headlines and provenance afterwards, aggregate method/counts/model identity, separate price/flow states and readable limitations. News & Analysis handoff selects the canonical instrument in Screener, including candidates outside the loaded grid, without inventing market values. Scope changes invalidate results; late responses cannot repaint a new scope. No execution or portfolio mutation was added.

## Validation ledger

Final review corrected cached Finviz publication-time parity and a shared-refresh receipt race: preview and Run now use the same detached receipt and canonical Eastern-wall-clock conversion. The new regression proves identical story timestamps/scores with zero preview provider/model work. A further provenance correction keys ingestion receipts by provider plus article identity and uses each provider cache snapshot independently of retrieval time. Its regression proves syndicated copies retain distinct ingestion clocks and future ingestion is excluded. The subsequent full attempt was deliberately interrupted to apply this correction; it is not an acceptance receipt. The earlier green FULL receipt below preceded these final backend corrections. Final canonical FULL passed on the corrected source: 7,838 tests, 7,785 passes, 53 skips, zero failures/errors in 394.232367s (71 suites).

- Expanded backend acceptance: 133 tests, zero failures/errors in 0.585s (OCT1-05, OCT1-04, S18 engines, S11 provider/cache/quota and News domain, OCT1-03 freshness, shared Anthropic budget).
- FAST: 23 tests, zero failures/errors/skips; 6.443454s. Observe-only SEVERE_REGRESSION against stored 1.821s baseline retained.
- Complete UI before final drilldown change: 1,281 tests across 168 files passed in 101.36s; final focused panel/page checks: 31 tests passed. Typecheck, lint, production build and bundle budget passed. Final complete UI passed 1,281/1,281 (168 files) in one worker; full and CI receipts follow below.
- Controlled actual UI/HTTP Chromium acceptance passed: explicit-only inference, cached preview, conflict/confirmation/mixed/unknown/unscored states, inspectable source/match/clocks/revision/probabilities, stale sentinel excluded, MSFT outside-page drilldown fully rendered, late scope response rejected, zero Paper/Live requests. Browser labels and model revision `rev001` are SOFTWARE_CONTROLLED, separate from the real local model below.
- Complete UI rerun while FULL was active: 1,277 passed / four App mode-navigation async failures (143.68s); all 76 App tests then passed isolated. No test timeout or unrelated UI was changed. A subsequent complete isolated run had 1,280 passes and one Live `/workspace/BIYA` heading timeout (136.322s). Final complete one-worker UI rerun passed all 1,281 tests across 168 files in 395.745s, with all assertions and timeouts unchanged. Default-concurrency CI remains required.
- Initial sandboxed CHANGED: 2,528 tests, 30 skips, zero failures, 13 errors in 190.957s; retained, not accepted as green or assumed baseline.
- Initial FULL: 7,835 tests, 53 skips, one failure and one error in 565.733042s. MATLAB governed smoke readiness transient and HTTP oversized-request WinError10053 both passed isolated rerun (two tests, 32.903s). No unrelated implementation or test was relaxed. Earlier pre-correction canonical FULL rerun passed: 7,836 tests, 7,783 passes, 53 skips, zero failures/errors in 551.393766s (71 suites).
- A focused command initially named nonexistent `test_screener_s18_engines`; corrected to `test_screener_s18`. New quote-plus-News test exposed a fixture evaluation-clock mismatch; corrected fixture clocks to the actual cutoff, then the expanded 133-test run passed.
- Controlled drilldown initially failed strict runtime schema because the HTTP fixture returned `FIXTURE` where the S11 contract accepts LOCAL_MODEL/PAID_API. Fixture corrected to LOCAL_MODEL with explicit simulated/software-controlled markers; complete drilldown then passed.

## Runtime provider acceptance â€” independent operational probes

Existing primary-checkout configuration was read without copying credentials into the worktree. Worktree-only initial FinBERT status NOT_CONFIGURED was not taken as workstation truth. Gates were preserved; no weights were installed/downloaded.

| Component | Actual result |
|---|---|
| FinBERT | Existing local weights; CURRENT, `ProsusAI/finbert`, revision `f6449ddda85e`; three controlled input sentences scored positive/negative/neutral with probabilities. One load and one inference batch. Cold load plus inference 29,130.621ms; warm cached batch 0.0497ms. This is real local inference, not live market outcome evidence. |
| NewsAPI | One guarded read for Apple; 96 items, DELAYED, Developer 24-hour delay/development-only restriction. 404.802ms; second read cache hit 0.0171ms; one provider request total. Shared persisted daily quota guard used. |
| Finnhub | One AAPL read; 243 items, CURRENT. 303.223ms; second read cache hit 0.0138ms; one request total. |
| Finviz | Credential available; live gate OFF, LIVE_DISABLED; zero network requests / live acceptance NOT_EXECUTED. |
| RSS | Canonical Federal Reserve feed probe returned LIVE_DISABLED (`IMP_NEWS_RSS_LIVE_NOT_SET`); zero network requests / live acceptance NOT_EXECUTED. |
| SEC | User agent not configured and live gate OFF; zero network requests / live acceptance NOT_EXECUTED. |

These instrument acquisition probes test existing providers independently. AI reduction itself does not call the instrument acquisition path.

## Bounds and performance

Maximum distinct controlled intake: 20 instruments, 60 unique clustered stories, one Finviz shared call across cold and warm runs, zero NewsAPI/Finnhub/SEC calls. One controlled sentiment load/batch, with warm scores cached. Shared projection 93.826ms cold / 91.208ms warm. Packet before News: 33,992 bytes / 13,999 estimated input tokens; after bounded thinning: 95,258 bytes / 34,655 estimated input tokens, three retained stories with explicit PACKET_LIMITED coverage elsewhere. Long-headline/unscored bound test: 94,825 bytes / 34,432 estimated tokens. Estimates include prompt/schema; they are not measured provider token usage.

Production bundle: initial 99.70 KiB gzip (same as OCT1-04); AI panel 5.32 KiB gzip. Largest existing lazy Vela chunk 870.73 KiB raw / 246.08 KiB gzip. Build 17.11s. FULL final 394.232s (earlier pre-correction green run 551.394s; initial failed run 565.733s) versus OCT1-04 542.343s and stored baseline 198.882s: SEVERE_REGRESSION retained; attribution unproved. No unrelated performance remediation.

## Genuine limitations and scope stop

Instrument provider coverage depends on caches warmed by the existing News workflow; cold candidate intake does not acquire per-symbol providers. A strict byte ceiling can remove all stories for some candidates; state and omission are explicit. Matching retains S11 keyword/identity limitations; context is not company-specific causal evidence. Unscored or weak stories remain inspectable but cannot produce directional alignment. Price change and four-hour language windows are explicitly different observations. Existing flow must already be owned and fully native; otherwise flow comparison is UNKNOWN. FinBERT cold load remains asynchronous in production.

No autonomous loop, order, execution, portfolio, new paid provider, model installation, forecast or strategy authority. OCT1-06 was not started.

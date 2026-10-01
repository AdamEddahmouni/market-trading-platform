# Screener free-capability activation

Date: 2026-09-29/30. Base: `main` at `9a455564` (after #439, final closure).
Scope: turn on every zero-cost capability the Main Screener already had but left
`NOT_CONFIGURED`. This work adds no universes, trading, paid plans or trials, and
commits no model weights. It also sends no key through chat, source, docs, tests or
logs.

This document replaces the "FinBERT, NewsAPI, Finnhub, AI synthesis:
`NOT_CONFIGURED`" and "Registry-dependent" observations in
[SCREENER_FINAL_CLOSURE.md](SCREENER_FINAL_CLOSURE.md).

## Audit (before any code)

| Capability | State before | Blocker | Cost | Terms | Can activate now? | Action |
|---|---|---|---|---|---|---|
| FinBERT sentiment | `NOT_CONFIGURED` (`IMP_FINBERT_MODEL_PATH_NOT_SET`) | No local model; torch/transformers not installed | $0 | Publisher repo Apache-2.0; trained on Financial PhraseBank (CC BY-NC-SA 3.0) | Yes | Pinned download to external cache, setup manifest, background load |
| Sentiment in News | Wired, never scored | FinBERT | $0 | — | Yes | Label scores `IMP_DERIVED_FINBERT`, report load state, fix Unicode crash |
| Finnhub Company News | `LIVE_DISABLED` | Free account key | $0 | Free tier: company news, North American companies, 1 year back; HTTP 429 over quota | Owner action | Hidden-input `auth.py configure`; state the plan terms; never call the premium News Sentiment endpoint |
| NewsAPI Developer | `LIVE_DISABLED` | Free account key | $0 | Development and testing only; articles delayed 24 h; 1 month back; 100 requests/day | Owner action | New `DELAYED` state (never `CURRENT`); daily quota survives restart; optional |
| AI synthesis | `NOT_CONFIGURED` (`ANTHROPIC_API_KEY_NOT_SET`) | Paid key was the only provider | $0 locally | llama.cpp MIT; Qwen3-4B Apache-2.0 | Yes | `LOCAL_MODEL` provider, loopback only, starts on request |
| Congress legislators registry | Needed a manual `IMP_CONGRESS_LEGISLATORS_PATH` | No refresh path | $0 | CC0-1.0 | Yes | Bounded cached refresh (7-day), background refresh behind `IMP_PUBLIC_RECORDS_LIVE` |
| House/Senate scanned PTR OCR | `SCANNED_UNPARSED` | Check marks, handwriting, 0.98 threshold | $0 | — | No | Keep `SCANNED_UNPARSED` (see OCR) |
| SEC EDGAR filings (instrument News) | `NOT_CONFIGURED` (`SEC_USER_AGENT_NOT_SET`) | Owner contact identity required by SEC fair access | $0 | SEC fair-access policy | Owner action | None in code; set in the API process environment |
| Senate eFD | Saved pages only | Interactive terms acceptance | $0 | 5 U.S.C. app. § 105(c) | Owner action | Unchanged (operator saves pages + attestation) |
| FRED / EIA / FINRA / OpenFIGI keys | `NOT_CONFIGURED` | Free account per provider | $0 | Per provider | Owner action | None; outside News/Sentiment/AI scope |

## Configuration resolution

Only the production singletons (`finbert_sentiment()`, `news_service()`,
`participant_service()`, the default synthesizer) resolve settings, in this order:

1. process environment;
2. `.private/providers.env` (`news.config.configured_value`), written by
   `python tools/news/auth.py configure` with hidden prompts;
3. setup manifests in the external IMP cache.

Injected constructors (all tests) never read any of these.

The external cache is `IMP_CACHE_DIR`, else `%LOCALAPPDATA%\IMP`, else
`~/.cache/imp` (`local_state/external_cache.py`). It holds `models/*.json`,
`runtimes/`, `registries/` and `quota/`. It is never inside the repository.

## FinBERT (local sentiment)

| Field | Value |
|---|---|
| Model | `ProsusAI/finbert` |
| Revision (pinned) | `4556d13015211d73dccd3fdd39d39232506f3e43` |
| Weights | `pytorch_model.bin`, 438,225,383 bytes, sha256 `e15a7b5738df7f17553399b6d94c6e2ff69c89245d066e8e5d183f5803a554e3` |
| Licence | The Hub card declares none. The publisher's repo (ProsusAI/finBERT) is Apache-2.0 and points to this copy. The training data (Financial PhraseBank) is CC BY-NC-SA 3.0: fine for a private non-commercial workstation, but review before any commercial redistribution. |
| Requirements | `torch` (CPU build) and `transformers`, optional and not in the dependency lock |
| Install | `python tools/news/setup_finbert.py` (explicit, one-time); `--check` verifies offline |
| Runtime | `local_files_only=True`; normal operation never downloads |

`model_revision` in API payloads is a hash of the loaded `config.json`, used as the
score cache key. The pinned Hub revision above is recorded in the setup manifest.

Measured on this workstation (Intel Core Ultra 7 256V, 15.5 GB RAM, CPU inference):

| Measure | Result |
|---|---|
| Cold first call | 10–50 s (imports ≈ 9 s; model load 0.5 s; varies with memory pressure) |
| Warm, one headline | ≈ 40 ms |
| Batch of 40 | 268–315 ms (6.7–7.9 ms each) |
| Resident memory after load | ≈ 0.9 GB |
| Loads per process | 1 |

Because the cold start is slow, the production singleton loads the model in a
background thread. Until it finishes, stories show `NOT_SCORED` with reason
`MODEL_LOADING` (UI: "model loading"). They are never shown as neutral.

Fixture results: a positive headline scores `POSITIVE` 0.92, a negative one
`NEGATIVE` 0.97, a neutral one `NEUTRAL` 0.95. "Beat estimates but guidance
disappointed" scores `NEGATIVE` 0.91. Empty text is `NOT_SCORED`. Malformed Unicode
(a lone surrogate) is now scored instead of failing the whole feed. Long text is
truncated to `MAX_TEXT_CHARS`, and a batch is classified in one call.

### Sentiment semantics

- Every score carries `basis: IMP_DERIVED_FINBERT`. IMP classified it locally; no
  news source supplied it. No provider sentiment is used. Finnhub's News Sentiment is
  premium and is never called.
- The status reports `runtime: LOCAL_MODEL`, plus `model_source` (`ENVIRONMENT`,
  `PROVIDER_ENV_FILE`, `SETUP_MANIFEST`).
- Sentiment describes headline language, not a forecast. It stays separate from AI
  synthesis.

## News providers

| Provider | Plan | State when working | Terms surfaced in `providers[].terms` |
|---|---|---|---|
| Finviz Elite | Existing subscription | `CURRENT` | — |
| RSS (official releases) | Public feeds | `CURRENT` | — |
| Finnhub | Free | `CURRENT` | `company-news`, North American companies, 429 over quota, 30 calls/s cap, $0 |
| NewsAPI | Developer | **`DELAYED`** (`NEWSAPI_DEVELOPER_PLAN_24H_DELAY`) | Development only, articles delayed 24 h, 100 requests/day, $0 |
| FinBERT | Local | `CURRENT` | Local model, $0 |

`DELAYED` counts as usable coverage but never as current. A view with only delayed
sources is `PARTIAL` / `ONLY_DELAYED_PROVIDERS`, and its analysis adds "Delayed
development-plan source (not current news)". NewsAPI is optional: nothing requires
it. The NewsAPI daily budget is persisted to `quota/newsapi-developer.json`, so a
restart cannot overspend it. A view requests at most once per TTL.

Keys are entered only with:

```bash
python tools/news/auth.py configure
```

The prompts are hidden; a blank entry skips that provider. Each entered key also
sets its `IMP_*_LIVE=1` opt-in. Restart the API afterwards.

## Local AI synthesis

| Field | Value |
|---|---|
| Runtime | llama.cpp `llama-server` b11269, Windows Vulkan x64 (MIT); zip sha256 `34a27c239727047adc5aed80b656b13373ff136b27d28bd898a14b7b7283695a` |
| Model | `Qwen/Qwen3-4B-GGUF` @ `bc640142c66e1fdd12af0bd68f40445458f3869b`, `Qwen3-4B-Q4_K_M.gguf`, 2,497,280,256 bytes, sha256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` (Apache-2.0) |
| Install | `python tools/news/setup_local_synthesis.py` (explicit, one-time, hash-verified, zip-slip guarded) |
| Provider | `local.openai_compatible`, `runtime: LOCAL_MODEL`, no credentials |
| Endpoint | `127.0.0.1:18089` only; non-loopback URLs are refused (`LOCAL_ENDPOINT_NOT_LOOPBACK`) |
| Lifecycle | Started on the first synthesis request; stopped after 15 min idle and at API exit |
| GPU | Vulkan0: Intel Arc 140V |

Selection (`select_synthesis_provider`): `IMP_SYNTHESIS_PROVIDER`
(`auto`/`anthropic`/`local`) is explicit. With `auto`, an Anthropic key selects the
paid API. Otherwise `IMP_LOCAL_LLM_BASE_URL` + `IMP_LOCAL_LLM_MODEL` select an
existing local server, and otherwise the setup manifest selects the managed server.
With none of these, the reason is `NO_SYNTHESIS_PROVIDER_CONFIGURED`.

### Grounding

- Decoding is schema-constrained (`output_json_schema`). `refs` is an enum of the
  packet's story ids, `observed_facts` needs at least one item, `uncertainties` is an
  array of strings, and extra keys are rejected. The validator is unchanged. Before
  the schema, the model returned `uncertainties` as a string and the output was
  correctly rejected (`INVALID_UNCERTAINTIES`).
- Unsupported certainty is still rejected. On the 20-story fixture the model
  repeated "will rally 30%" without quoting it, and the result was
  `UNSUPPORTED_CERTAINTY`.
- `story_ids` names exactly the stories the model saw (at most 12). The response's
  `coverage.synthesized_story_count` states that number next to the matched
  `story_count`, and the UI shows "12 of 21 stories".
- Synthesis runs only on an explicit request (a POST with `state.write`). The UI
  aborts an in-flight request when the selection changes or the panel unmounts.
- Error states: `LOCAL_MODEL_UNAVAILABLE`, `LOCAL_MODEL_TIMEOUT`,
  `LOCAL_MODEL_HTTP_<n>`, `LOCAL_MODEL_RESPONSE_MALFORMED`, and the
  `LOCAL_RUNTIME_*` start failures.

### Measurements

| Measure | Result |
|---|---|
| Server start | 13.2 s cold, 5.1 s warm |
| 5-story synthesis (fixture) | 16–35 s; `CURRENT`, refs s1/s2/s4/s5 only, conflict identified, uncertainties listed |
| 20-story synthesis (fixture) | Rejected `UNSUPPORTED_CERTAINTY` (correct) |
| Live BTC/USD (21 matched, 12 used) | 45.7 s cold start included; `CURRENT`, 3 facts, 1 conflict, refs valid |
| Live 10-year Treasury note (11 stories) | 32.0 s; `CURRENT`, refs valid |
| Live NVDA (4 stories) | 30.0 s; `CURRENT`; states the coverage is sparse |
| Repeat request (cache hit) | ≈ 1 s round trip |
| `llama-server` working set | 0.4–4.2 GB |

After the API stopped, no `llama-server` process remained.

## Paid Claude synthesis (optional, budgeted)

With an Anthropic key configured, `IMP_SYNTHESIS_PROVIDER=auto` (the default) uses
Claude for synthesis, and the local model stays the fallback.
`IMP_SYNTHESIS_PROVIDER=local` turns paid calls off entirely. Sentiment stays on
FinBERT: it runs per headline on every feed load, where a paid model would add cost
and latency for no better label.

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Entered with `python tools/news/auth.py configure` (hidden) or the operator config screen; stored in `.private/providers.env` |
| `IMP_SYNTHESIS_ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Synthesis model (independent of the assistant's `ANTHROPIC_MODEL`); `claude-haiku-4-5-20251001` is the cheaper option |
| `IMP_SYNTHESIS_DAILY_REQUESTS` | 30 | Hard per-UTC-day request limit |
| `IMP_SYNTHESIS_DAILY_TOKENS` | 200,000 | Hard per-UTC-day token limit (input + output) |

Safeguards (`intelligence/inference/anthropic_synthesis.py`):

- **Hard daily budget.** Before each call, the worst case (prompt estimate + tool
  schema + `max_tokens`) is reserved. A call that could cross either limit is refused
  before any request is sent (`SYNTHESIS_DAILY_REQUEST_LIMIT` /
  `SYNTHESIS_DAILY_TOKEN_LIMIT`). The count persists in
  `<IMP cache>/quota/anthropic-synthesis.json`, so a restart does not reset it. The
  panel shows today's usage, and at the limit the AI status reads
  `SYNTHESIS_DAILY_BUDGET_EXHAUSTED`.
- **Accurate charging.** Reported usage replaces the reservation. Refusals (401/403,
  400, overload) charge nothing, and a timeout keeps the worst case charged.
- **No retries.** A 429, overload, timeout or truncated answer is shown once as a state
  (`ANTHROPIC_*`), never retried automatically.
- **No re-billing.** Identical concurrent requests share one call. A rejected answer is
  cached for 30 minutes (temperature 0 would repeat it), and a transient failure for
  60 s. A budget refusal is not cached, so raising a limit takes effect at once.
- **Structure first.** A forced tool whose input schema limits `refs` to the packet's
  story ids makes rejected-but-billed answers rare. `max_tokens` is 2,048 (a cap, not a
  charge) so answers are not truncated, and the timeout is 45 s.

## Congress legislators registry

| Field | Value |
|---|---|
| Source | `unitedstates/congress-legislators` (gh-pages), CC0-1.0 |
| Revision | `577ca04282d14688cb14f6559eb27b52bdc50dfc` (2026-09-24) |
| Kept | 539 current + 607 historical (terms ending on or after 2012-01-01) = 1,146 |
| Cache | `%LOCALAPPDATA%\IMP\registries\congress-legislators` (+ manifest with sha256, bytes, ETag, Last-Modified) |
| Refresh | `python tools/congress/refresh_legislators.py` (or `--check`); the API refreshes in the background every 7 days only when `IMP_PUBLIC_RECORDS_LIVE=1` |
| Failure | Stable codes (`REGISTRY_HTTP_n`, `REGISTRY_INVALID_JSON`, …). A failed refresh keeps the previous copy. |

An explicit `IMP_CONGRESS_LEGISLATORS_PATH` still wins and is never refreshed. The
participants coverage shows `identity.registry_status` (CURRENT / STALE / MISSING /
UNREADABLE).

## OCR decision

Kept `SCANNED_UNPARSED`. The closure's Tesseract run reached a median word
confidence of about 96, and no page reached the 0.98 threshold. It also could not
read check-mark columns (transaction type, amount band) or handwriting. Another
free OCR engine would not read check marks or handwriting either, and lowering the
threshold would turn scanned filings into guessed transactions. No OCR engine is
installed here, and none was added. Scanned filings stay linked.

## Live acceptance (2026-09-30, worktree API on port 8877)

Live gates used for the run: `IMP_LIVE_OBSERVATIONAL`, `IMP_MOOMOO_LIVE`,
`IMP_FINVIZ_LIVE`, `IMP_NEWS_RSS_LIVE`, `IMP_EDGAR_LIVE`,
`IMP_PUBLIC_RECORDS_LIVE`, `IMP_TREASURY_LIVE`, `IMP_CRYPTO_LIVE`, and
`IMP_SENATE_EFD_IMPORT_DIR` (the owner's saved pages). No NewsAPI, Finnhub or SEC
User-Agent was set, and no key exists on the workstation.

| Universe | Feed | Stories (sources) | FinBERT | Instrument check |
|---|---|---|---|---|
| US Equities | `CURRENT` | 91 (Finviz 91) | 91 scored: 23 positive / 57 neutral / 11 negative | AAPL: 2 stories, 2 scored; NVDA: 4 stories, 4 scored. `PARTIAL`: NewsAPI/Finnhub `LIVE_DISABLED`, SEC `SEC_USER_AGENT_NOT_SET` |
| ETFs | `PARTIAL` / `OPEND_UNAVAILABLE` | 0 | — | Catalog needs moomoo OpenD (not running); providers `CURRENT` |
| Futures | `PARTIAL` / `OPEND_UNAVAILABLE` | 0 | — | Same as ETFs |
| Bonds | `CURRENT` | 11 (Finviz 3, RSS 9) | 11 scored: 4 positive / 7 neutral | 10-year note: 11 stories, issuer-level context |
| Crypto | `CURRENT` | 26 (RSS 25, Finviz 1) | 26 scored: 9 / 12 / 5 | BTC/USD: 21 stories, 21 scored |

On the first request after start, every story was `NOT_SCORED` / `MODEL_LOADING`.
About 20 s later the model was loaded and all stories were scored. The UI tests
cover rapid symbol switching and synthesis cancellation.

Congress identity with the cached registry:

| Chamber | Before (closure) | After |
|---|---|---|
| Senate (3 saved reports, 44 transactions) | 34 official, 10 unresolved | 44 `OFFICIAL_ID` |
| House (132 filings, 1,040 transactions, 801 in universe) | Official via manual path | 801 `OFFICIAL_ID`; 1 `SEAT_AND_NAME` outside the universe |

## Owner actions (all free)

1. Create a free Finnhub key and, optionally, a NewsAPI Developer key. Then run
   `python tools/news/auth.py configure` and restart the API. Never paste keys in
   chat or commit them.
2. Set `SEC_USER_AGENT` (name + contact) in the API process environment for
   instrument SEC filings.
3. ~~Senate eFD: accept the terms in a browser and save more PTR report pages into
   the import directory.~~ Automated 2026-09-30 (owner decision): with
   `IMP_SENATE_EFD_LIVE=1`, IMP accepts the terms and downloads new reports every
   6 h ([S14 automatic download](SCREENER_S14_DISCLOSURE_COVERAGE.md#automatic-download-2026-09-30)).
   Owner steps left: set `IMP_SENATE_EFD_IMPORT_DIR` and `SEC_USER_AGENT`.
4. ~~Decide whether the standard launcher should enable the source gates by
   default.~~ Decided 2026-09-30 (owner): `tools/platform/local_launcher.py` turns on
   every observational data-source gate (`PROVIDER_SOURCE_GATES`) at launch. An
   explicit value in the environment still wins. The gates only permit reads. A
   source that also needs a key, a `SEC_USER_AGENT` or saved pages keeps reporting
   `NOT_CONFIGURED` without it. IBKR and recorded order-flow replay are not
   data-source gates and stay off.
5. Start moomoo OpenD for the ETF and Futures catalogs.

## Actionable degraded states and Setup

Degraded states stay truthful: every reason code is still returned and shown on hover.
Beside it, the server now attaches a `remedy` (`title`, `step`, optional `action`) from
one table in `ui_api/screener_remedies.py`. The UI renders that instead of a bare code:

- **Feed and empty state.** An ETF or Futures feed whose OpenD catalog is down
  (`PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`) reads "moomoo OpenD isn't running.
  Start OpenD and log in to load ETFs." with a **Start OpenD** button. Provider rows
  carry their own step (`SEC_USER_AGENT_NOT_SET`, the `*_LIVE_NOT_SET` gates, missing
  keys, FinBERT and local-model install), shown once per distinct cause.
- **Setup panel.** `GET /screener/setup` lists OpenD, NewsAPI, Finnhub, public RSS, SEC
  EDGAR, public records, Senate eFD pages, FinBERT and AI synthesis with state and the
  one enabling step. It reuses the existing gates and status builders; the only probe is
  the OpenD check, cached for 15 s. The panel is offered in every universe.
- **Connect.** `POST /screener/providers/{id}/connect` (`state.write`, operator click
  only) is a strict allowlist: `opend` starts the installed
  `%APPDATA%\moomoo_OpenD\moomoo_OpenD.exe` through the existing `diagnose_opend(start=True)`
  and invalidates the cached ETF/Futures catalogs and news indexes; `finbert` starts
  the background model load; `local_synthesis` starts the loopback model server off the
  request thread. Anything else is `PROVIDER_NOT_CONNECTABLE`. It never downloads,
  installs, or accepts keys or flags. Live panels (Order Flow, CVD, Level 2, Charts)
  show the same Start OpenD button on `OPEND_UNAVAILABLE`.
- **Recovery without a click.** A failed OpenD catalog is retried after 30 s instead of
  15 min, and a news index built on a failed catalog after 30 s instead of 10 min, so
  OpenD finishing its login shows up within a poll.
- **Model loading resolves itself.** While the sentiment model reports `MODEL_LOADING`,
  the News view and News & Analysis panel re-poll every 4 s (for at most 3 min), then
  return to the 60 s cadence once stories are scored.

## Restrictions kept

- No paid plans, trials or billing. NewsAPI Developer is labelled development-only
  and delayed.
- No premium endpoints (Finnhub News Sentiment).
- No model weights, runtimes or registry data in Git; all go to the external cache.
- No silent downloads: model setup is explicit, and runtime is `local_files_only`.
- The local model endpoint is loopback only.
- ~~No automated Senate eFD access in IMP.~~ Superseded 2026-09-30: automated,
  throttled and attestation-gated (see item 3 above).

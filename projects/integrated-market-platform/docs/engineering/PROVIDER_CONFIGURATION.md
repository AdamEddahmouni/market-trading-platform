# Provider configuration (Setup)

How the operator sets provider keys, tokens, and the SEC contact identity from the IMP UI,
where they are stored, and what IMP deliberately does not accept.

**Authority:** `src/market_platform_foundation/ui_api/operator_config.py` (`PROVIDERS`) is the
only allowlist. This page describes it; the code controls.

## Operator path

Screener → **Setup** panel → **Provider settings**. Providers are grouped (Regulatory,
News, Market data, AI, Local services, Brokerage); groups with something to set up open
on their own. Each row shows its state, whether it is free, a free account, a paid API,
or an existing subscription, and what it unlocks. **Configure** / **Manage** opens a
form for that provider.

The same form opens from any degraded state whose remedy is a missing credential: a
remedy with `action.kind = "CONFIGURE"` (`screener_remedies.py`) renders a button (for
example **Set SEC identity** beside `SEC_USER_AGENT_NOT_SET` in News, or **Enter key**
beside `OPENAI_API_KEY_NOT_SET` in the AI engine picker).

Terminal fallback, same validation and storage:

```
python tools/news/auth.py configure                     # SEC identity, NewsAPI, Finnhub, AI keys
python tools/news/auth.py configure --provider finra    # any configurable provider below
```

The Control page's advanced credential grid uses the same endpoint and registry.

## Inventory

Legend: **Secret** values are never returned by any API. Gates are observational read
gates switched on when the provider becomes fully configured.

| Provider | Setting | Kind | Secret | Required | Gates on save | Applies | Unlocks |
|---|---|---|---|---|---|---|---|
| SEC EDGAR | `SEC_USER_AGENT` | contact identity | no (PII: status shows the email domain only) | yes | `IMP_EDGAR_LIVE`, `IMP_SEC_FTD_LIVE` | next request | SEC filings in News; SEC press releases; 13F ownership; fail-to-deliver (Short Squeeze); automatic Senate eFD downloads (with the attested folder) |
| NewsAPI | `NEWSAPI_API_KEY` | API key | yes | yes | `IMP_NEWSAPI_LIVE` | next request | NewsAPI headlines |
| Finnhub | `FINNHUB_API_KEY` | API key | yes | yes | `IMP_FINNHUB_LIVE` | next request | Finnhub company news |
| FINRA API | `FINRA_CLIENT_ID`, `FINRA_CLIENT_SECRET` | client ID, client secret | secret only | both | `IMP_FINRA_LIVE` | next request | short interest, short-sale volume |
| FRED | `FRED_API_KEY` | API key | yes | yes | `IMP_FRED_LIVE` | next request | macro and rates context |
| EIA | `EIA_API_KEY` | API key | yes | yes | `IMP_EIA_LIVE` | next request | energy context |
| OpenFIGI | `OPENFIGI_API_KEY` | API key | yes | optional | — | next request | higher lookup limit (works without) |
| NOAA CDO | `NOAA_CDO_TOKEN` | token | yes | optional | — | next request | historical climate data (NWS works without) |
| Finviz Elite | `FINVIZ_API_KEY` | token | yes | yes | — | **restart** | Finviz screens, news, fundamentals (existing subscription) |
| Anthropic | `ANTHROPIC_API_KEY` | API key | yes | yes | — (paid) | next request | Claude synthesis engine |
| OpenAI | `OPENAI_API_KEY` | API key | yes | yes | — (paid) | next request | OpenAI synthesis engine |
| Google Gemini | `GEMINI_API_KEY` | API key | yes | yes | — (paid) | next request | Gemini synthesis engine |
| Tradier paper sandbox | `IMP_TRADIER_TOKEN`, `IMP_TRADIER_ACCOUNT_ID` | token, account ID | token only | both | — | **restart** | sandbox paper account, only when paper routing is separately enabled |

Paid AI keys switch on no gate and are never probed: synthesis runs only on an explicit
request, on the engine the operator picks, under the shared daily synthesis budget. They
are also never copied into the API's process environment (`process_names()`): synthesis
reads the private file itself, and a key in the environment would silently switch the
Assistant to paid Anthropic (`assistant/inference_factory.py`).

### Not accepted through the UI (by design)

| Provider / setting | How it is set up | Why not a form field |
|---|---|---|
| moomoo OpenD | Start from the Setup checklist, log in inside OpenD | A local process with its own login; no key exists |
| IBKR (`IBKR_USERNAME`, `IBKR_PASSWORD`, `IBKR_TOTP_SECRET`) | IB Gateway / TWS sign-in with IBKR two-factor | Brokerage passwords and 2FA seeds must not sit in a plaintext file. No runtime code reads them; the earlier Control-page fields were removed. Values already on disk are left untouched. |
| Senate eFD (`IMP_SENATE_EFD_IMPORT_DIR`, `ACCESS_ATTESTATION.json`) | Operator's folder and signed attestation | Terms acceptance is a legal act by the operator (S14 contract); the form does not accept terms |
| Assistant provider (`IMP_ASSISTANT_PROVIDER`, `ANTHROPIC_MODEL`, and an Anthropic key for the Assistant) | API environment or repository `.env` | Moving the Assistant onto a paid API is a separate, explicit decision; the earlier Control-page fields were removed because the Assistant reads only the process environment |
| Execution gates (`IMP_TRADIER_PAPER`, `IMP_BROKER_PAPER_EXECUTION`, `IMP_PAPER_EXECUTION`, …) | API environment | Authority, not configuration; never switched by a credential save |
| Alpaca / moomoo paper keys (`APCA_*`, `IMP_MOOMOO_PAPER_*`) | API environment | Execution-adjacent research/calibration credentials |
| Finviz login (`FINVIZ_USERNAME`, `FINVIZ_PASSWORD`) | Finviz secure store | Account passwords; the Elite token above covers the API |
| User-Agent overrides (`CFTC_USER_AGENT`, `IMP_NWS_USER_AGENT`, `IMP_CBOE_OPTIONS_USER_AGENT`) | API environment | Optional; safe defaults exist |
| Market-data entitlements, subscriptions | The provider's own site | Not a credential; IMP has no purchase flow |

## Storage and precedence

Highest first:

1. **Environment**: the API's process environment as it was *before* IMP loaded any file.
   Setup shows these as "Set by the API's environment" and refuses to write them
   (`409 SETTING_OVERRIDDEN_BY_ENVIRONMENT`), so there is never a shadow value that
   silently does nothing. The launcher's default gates (`PROVIDER_SOURCE_GATES`) are in
   this layer.
2. **Private file**: `.private/providers.env` (or `IMP_PROVIDER_ENV`). Written by Setup
   and the CLI. Git-ignored. Only registered lines are touched; every other line,
   comment, and order is preserved. Writes are atomic (temp file, fsync, replace).
3. **`.env`**: the repository `.env`, loaded by the API launcher.

Most provider code reads `os.environ`. At API start (`tools/ui1/run_ui_api.py --serve`)
`bootstrap_process_environment()` snapshots which registered names the real environment
sets, then copies registered private-file values (except paid-API keys) into the process
environment without overriding it, before `.env` loads. Before this change `.private/providers.env` reached
only the News/AI readers (`news.config.configured_value`); FRED, EIA, FINRA, Tradier,
SEC, and Finviz values saved there were never read.

## Write API

`POST /operator/config/provider` (capability `security.config.write`):

```json
{ "provider": "sec", "values": { "SEC_USER_AGENT": "…" }, "clear": [] }
```

- Only a registered, configurable provider and its own settings; any other name is
  `PROVIDER_FIELD_NOT_ALLOWED`. Gates are policy, not writable fields. There is no
  generic environment write.
- A blank value keeps what is stored. `clear` removes named settings; when a provider
  loses all its required settings its private-file gate lines are removed too.
- Validation (`operator_config.py`): no control characters, no surrounding quotes, no
  placeholders, length limits; keys/tokens/ids are one run without whitespace (provider
  formats are not guessed). `SEC_USER_AGENT` must pass the SEC transport's own rule
  (`require_user_agent`) plus a real email and a readable name, printable ASCII,
  at most 200 characters.
- Errors are `CODE` or `CODE:SETTING`, never a value (the textual leak rules match
  `NAME=value`, so the code leads).
- Browser pages on another site are refused (`403 OPERATOR_CONFIG_ORIGIN_REJECTED`)
  from `Origin`/`Sec-Fetch-Site`: the API answers every origin (CORS `*`), so without
  this any web page could replace a key while the platform runs.
- The response is the value-blind status plus `result` (names saved, cleared, gates
  switched, `applies`, `verification: ON_FIRST_USE`).

## Reload

A save updates the process environment immediately and drops clients that captured the
old value, only in services that already exist:

- `news_service().credentials_changed()`: SEC filings transport, RSS feed cache (including
  a cached `NOT_CONFIGURED`), the AI synthesizer, universe indexes.
- `participant_service().credentials_changed()`: the SEC transport used for 13F and
  Senate sync.
- FTD, FINRA, FRED, EIA, OpenFIGI, NOAA and the News key readers read at request time.
  Cached results expire on their normal TTL.
- **Restart required** (stated in the form): Finviz (token read at startup) and Tradier
  (adapter built at startup).

No provider is called to "test" a saved value. Setup says so: it is checked the first
time IMP uses it.

## Security invariants

- No API response contains a stored secret; `GET /operator/config` returns
  `configured`, `source`, `editable`, `removable`, and for the SEC identity only the
  email domain. Every response still passes `assert_no_secrets_in_payload`.
- A secret travels only in the body of an explicit save. The UI holds it in form state
  until the request completes, then clears it; it never uses a query cache, mutation
  cache, `localStorage`, `sessionStorage`, or a URL for it. Inputs are `type=password`,
  `autocomplete=off`.
- Values are never logged or printed (the CLI prints setting names only).
- Saving a credential never enables execution, billing, a subscription, or broker
  authority; the registry's gates are all `IMP_*_LIVE` read gates and a test enforces it.

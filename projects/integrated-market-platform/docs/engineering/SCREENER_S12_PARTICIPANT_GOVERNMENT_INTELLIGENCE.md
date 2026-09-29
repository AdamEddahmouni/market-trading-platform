# Screener S12 — Institutional, Whale, Congressional & Government Intelligence

Status: **implementation and local validation complete (S12, 2026-09-29)** — built on `main` after
[Screener S11](SCREENER_S11_NEWS.md) (S1–S11 merged).

## Validation

Final canonical changed validation, 2026-09-29, on commit `1071d39` (the
handoff commit; no product code changed afterwards), Linux cloud container,
Python 3.11.15, Node 22.22.2, live provider gates unset, no Moomoo OpenD, IBKR,
or MongoDB:

```
python tools/imp.py validate changed --paths-file <git diff --name-only origin/main HEAD> --json <report>
```

The branch was fully committed, so the changed set came from the same
base..head diff the GitHub workflows use (69 paths).

| Gate | Result |
|------|--------|
| `validate changed` | **PASSED**, exit 0: 33 suites, 5,884 tests, 5,841 passed, 43 skipped, 0 failures, 0 errors, 208 s (02:30:45–02:34:14 UTC); `core_checkpoint_required=true` (a `validate full` closure was not run, as for S11) |
| `validate fast` | passed, 23 tests |
| `format`, `lint`, `tools/check_docs_links.py` | passed (276 governance markdown files) |
| UI `npm test` | 154 files, 1,153 tests passed |
| UI `npm run typecheck`, `npm run build` | passed; initial JS 201.40 KiB gzip (budget 203 KiB) |

The 43 skips are environmental and none is an S12 test: 20 MongoDB
integration tests (`IMP_TEST_MONGODB_URI` unset), 6 environment-unavailable,
2 Windows job-object tests, local demo servers, run directories, and
fixtures absent on this host.

Earlier attempts and their classification:

- A completed Windows run on the developer machine reported one failure and
  one error. The validation-manifest directory count (71 → 72 for the new
  `public_records` tests) was an S12 test expectation and was corrected before
  the handoff commit. The detached-supervisor acceptance test's
  `TemporaryDirectory` cleanup hit a Windows file lock (WinError 32); it passed
  on two isolated reruns and passed in the cloud run above. Later Windows runs
  were interrupted with no result.
- The first cloud run (exit 1) failed three
  `tests/intelligence/test_release_governance.py` tests with
  `INCOMPATIBLE_EVIDENCE_LINEAGE`: the cloud clone was shallow, so the
  BUILD34 evidence commit that the release SHA must descend from was absent.
  After `git fetch --unshallow` the same three selectors passed with no code
  change, and the complete rerun above passed. Environment, not S12.

S12 is a cross-universe **intelligence layer**, never a universe. The registry
still holds exactly five universes (`US_EQUITIES`, `US_ETFS`, `FUTURES`,
`BONDS`, `CRYPTO`; see
[SCREENER_UNIVERSE_ARCHITECTURE.md](SCREENER_UNIVERSE_ARCHITECTURE.md)), and
`tests/platform/test_screener_s12.py` pins that no participant, congress, or
government universe exists.

S12 shows **public records as filed**, in four evidence families that are never
blended:

| Family | Evidence | Official source |
|--------|----------|-----------------|
| Institutional | Form 4 insider transactions, Schedule 13D/13G beneficial owners, 13F quarter-end holdings | SEC EDGAR (daily form index, submissions, filing documents), SEC Form 13F data sets |
| Whale | CFTC Commitments of Traders categories (futures); large prints link to Order Flow with the participant **unknown** | CFTC Public Reporting; the S4 Order Flow panel |
| Congressional | House Periodic Transaction Reports (PTRs) | House Clerk financial-disclosure index and PDFs |
| Government | Federal contract and assistance actions; Lobbying Disclosure Act filings | USAspending.gov; lda.gov |

There is **no** Smart Money, Whale, Congress, ownership, or influence score, no
ranking of members, no party, and no inferred motive.

## Surfaces

| Surface | Where | Request |
|---------|-------|---------|
| **Institutional** view (`intel=ownership`) | US Equities views tablist, after News | `GET /screener/participants/ownership` |
| **Congress** view (`intel=congress`) | US Equities and ETFs | `GET /screener/participants/congress` |
| **Positioning** view (`intel=positioning`) | Futures | `GET /screener/participants/positioning` |
| **Institutional & Whale** dock panel (`institutional`) | US Equities, ETFs, Futures | `GET /screener/participants/instrument?lens=institutional` |
| **Congress & Government** dock panel (`congress_gov`) | US Equities, ETFs | `GET /screener/participants/instrument?lens=congress_gov` |
| Quick Preview **Participants** tab | wherever either panel is offered | `…/instrument?…&compact=1`, with "Open …" actions |

Intelligence views are views **inside** the active universe. Their URL state
uses its own params (`intel`, `iwin`, `isort`, `ifam`, `itype`, `iamt`, `imem`,
`ioff`) so column-view, sort, News, and saved-screen params keep their meaning.
Choosing a column view or News leaves the intelligence view; a universe switch
keeps it only when the next universe offers it (filters and page reset).

Bonds and Crypto have no S12 surface: none of these families is a
universe-complete record for them.

## Architecture

```
official sources                    domain parsers (pure)                      read model                         UI
---------------------------------   ----------------------------------------   --------------------------------   --------------------------
SEC daily form index / submissions  sec_edgar/ownership.py (Form 4, 13D/G,     ui_api/screener_participants.py    api/screenerParticipants.ts
SEC 13F data sets (local build)       index grouping, subject role)            ScreenerParticipantService:          (zod, identity guards)
CFTC Public Reporting               sec_edgar/thirteen_f_index.py (SQLite)      - universe views                   participants/IntelligenceView
House Clerk index + PTR PDFs        cftc/screener_positioning.py               - instrument lenses                panels/InstitutionalPanel
USAspending.gov                     congressional_ptr/house.py (index, PDFs)   - BackgroundCache per source        panels/CongressGovPanel
lda.gov                             public_records/{usaspending,lobbying}.py   - states, clocks, boundaries        participants/PreviewParticipants
```

- Every network source runs **off the request thread** through the S8
  `BackgroundCache`; a request waits at most `PROVIDER_WAIT_S` (6 s) and
  otherwise returns `PENDING` for that section. The UI re-reads pending or
  partial payloads after 10–15 s and settled ones every 5 minutes.
- The universe catalog used for matching is also loaded off-request (10-minute
  TTL). A catalog still loading makes a view `PENDING · UNIVERSE_INDEX_LOADING`;
  a failed catalog makes it `SOURCE_ERROR` — never "no disclosures".
- Government sources for one instrument (USAspending, its publication stamp,
  LDA) start together, so a cold panel waits for the slowest source, not the sum.
- `public_records/http.py` paces each host separately (0.5 s minimum interval)
  and waits **outside** its lock, so the House PDF loader never delays
  USAspending or LDA requests.
- Routes are `GET` only (`state.read`); invalid parameters return
  `400 SCREENER_PARTICIPANTS_INVALID`, an unknown instrument
  `404 SCREENER_PANEL_UNKNOWN_INSTRUMENT`. Every response passes the server's
  secret-leak audit.
- The UI requests only for an entered view, a visible panel, or an open Preview
  tab, for the **settled** selection — never per row.

## States

Every overall, section, provider, and filing state is one of:

| State | Meaning |
|-------|---------|
| `PUBLICATION_CURRENT` | the latest official publication is loaded (PTR index, COT, USAspending, LDA) |
| `CURRENT_AS_FILED` | filings are current as filed (SEC) |
| `STALE` | reserved in the contract for an older copy shown while a refresh fails; S12 sources currently report a failed refresh as `SOURCE_ERROR` |
| `PARTIAL` | some sources or documents are missing; the missing ones are named |
| `NOT_CONFIGURED` / `LIVE_DISABLED` | a gate or credential is not set — a source state, **not** an absence of disclosures |
| `UNAVAILABLE` / `SOURCE_ERROR` | the source failed; the reason code is shown |
| `NO_MATCH` | the instrument has no exact identity in the source (e.g. ticker not in the SEC map) |
| `NO_DISCLOSURES` | the source is current and holds nothing for this scope |
| `PENDING`, `NOT_LOADED`, `NOT_APPLICABLE`, `SEE_ORDER_FLOW` | loading; not loaded in the compact preview; not applicable to the universe; see the Order Flow panel |

A panel's overall state names the evidence state (`CURRENT_AS_FILED` for
filings, `PUBLICATION_CURRENT` for publications; a mix reports the narrower
`CURRENT_AS_FILED`); any source state makes it `PARTIAL`. The panel header shows
plain language ("Current as filed"), never the code.

## Time semantics and anti-lookahead

Clocks are kept apart and every row carries its own:

- **SEC:** filing date from the daily index (date only — the index has no
  time); acceptance time from EDGAR submissions for per-instrument filings;
  transaction or event dates from the documents. Availability is the
  acceptance time.
- **13F:** quarter-end period, filing date, and availability. A holder is shown
  only from reports filed before the cutoff (the day before the request); a
  later restatement never rewrites an earlier view. `EXITED` is claimed only
  when the manager filed the current period. Until period + 45 days the section
  is `PARTIAL · FILING_WINDOW_OPEN`.
- **CFTC:** positions as of the report date (Tuesday); public from the official
  release time (normally Friday 15:30 ET, holiday-delayed per the CFTC
  schedule).
- **Congress:** transaction date, notification date, filing date, and
  `available_at` = the later of the end of the filing day (UTC) and IMP's first
  retrieval. Windows select by **filing date**. Disclosure lag is DERIVED
  (transaction → filing, calendar days) and unknown when a date is missing.
  *Superseded by [S14](SCREENER_S14_DISCLOSURE_COVERAGE.md):* `available_at` is the end of the **Eastern** filing day
  (the UTC bound was 4–5 hours early), and first retrieval is kept as a separate
  clock (`imp_known_at`) instead of moving availability.
- **USAspending / LDA:** action date or filing period, plus the source's
  publication stamp.

## Evidence boundaries and neutrality

Shown with every surface:

- A 13F holding is a quarter-end position disclosed weeks later, not a live position.
- A congressional transaction date is not its disclosure date; the amount is a disclosed range, not an exact size.
- A government award or grant is not revenue and not a bullish signal; lobbying is not government support.
- A large print is market activity with an unknown participant; it is not an institution or accumulation.
- CFTC positioning describes reported categories; it is not a price forecast.

Congressional amounts are **bands** (`exact_value_disclosed: false`; the UI
contract rejects a point value). Members are listed as named in the Clerk's
index (e.g. "Richard Dean Dr McCormick" is the index's own spelling); party is
not part of the index and is not shown. ([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md) adds a canonical member identity
beside the filed spelling, merged only on official-id or same-seat evidence.) Award sums are DERIVED, signed
(de-obligations subtract), and shown only when every action in the window is
listed. Lobbying income (outside firms) and expenses (in-house) are never added
together.

## Families in detail

### Institutional

- **Ownership view:** Form 4 and Schedule 13D/13G filings from the last 1–10
  business days of daily indexes, matched to the universe by SEC CIK. A filing
  that names two listed companies (e.g. a holding company and its own filer
  entity) is marked `role unverified` rather than assigned. Self-submitted
  13D/13G (a company reporting its stake in *another* issuer) are excluded from
  the issuer's rows.
- **Panel:** 13D/13G reporting persons with percent of class as of the event
  date (joint filers are never summed); Form 4 transactions with codes, prices,
  holdings after, and 10b5-1 flags; P/S/other code counts (DERIVED); 13F top
  holders with quarter-over-quarter change classes; recent ownership filings;
  large activity → Order Flow.
- **13F index:** built locally from SEC Form 13F data-set ZIPs into SQLite
  (per-accession storage; query-time point-in-time selection; put/call and
  principal-amount lines excluded from share aggregates). Issuer CUSIPs come
  from 13D/13G cover pages.

### Whale (futures)

CFTC Traders in Financial Futures and Disaggregated reports (futures only) by
mapped root: category long/short/spreading, DERIVED net, the CFTC's published
weekly changes, and trader counts. The two report types' categories are never
mapped onto each other. Unmapped roots are named.

### Congressional

House PTRs from the Clerk's annual index; machine-readable PDFs are parsed,
scanned ones are counted and linked (open on the Clerk site). Matching uses
the **disclosed ticker** and asset type only (options flagged). Senate eFD
requires interactive terms acceptance and is **not integrated**; it is
reported as `NOT_CONFIGURED` on every surface. ([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md): scanned filings are
`SCANNED_UNPARSED` with document classes and parse states; Senate reports can be
imported by the operator after accepting eFD's terms, and the provider reports
`TERMS_ACCEPTANCE_REQUIRED` until then.)

### Government (US equities only)

USAspending contract and assistance actions for the company's recipient name
(last 90 days; parent-linked recipients included and named per row), and LDA
filings naming the company as client (this year and last). Generic
single-word names are refused (`ENTITY_NAME_TOO_GENERIC`) rather than matched
loosely. ETF panels show congressional disclosures only.

## Configuration

| Variable | Purpose |
|----------|---------|
| `IMP_EDGAR_LIVE=1` | enable SEC EDGAR requests |
| `SEC_USER_AGENT` | required by the SEC: a name and a contact email (e.g. `IMP Screener you@example.com`); sent only to SEC hosts; never committed |
| `IMP_PUBLIC_RECORDS_LIVE=1` | enable House Clerk, USAspending, and LDA requests |
| `IMP_13F_INDEX_PATH` | path to a locally built 13F index (optional; without it the 13F section is `NOT_CONFIGURED · THIRTEEN_F_INDEX_NOT_BUILT`) |

The CFTC client is the existing S5 path. No credential, cookie, or session
token is used for any S12 source.

### Building the 13F index

> Superseded for routine use by the managed lifecycle in [S14](SCREENER_S14_DISCLOSURE_COVERAGE.md)
> (`tools/sec_edgar/thirteen_f_refresh.py`, `IMP_13F_DATA_ROOT`). The manual build
> below still works and is served as `UNMANAGED`.

Download the quarterly *Form 13F data sets* ZIPs from sec.gov (each covers
about three months of filings) and build the index **outside the repository**:

```
python tools/sec_edgar/thirteen_f_index.py --zip 01mar2026-31may2026_form13f.zip --zip 01jun2026-31aug2026_form13f.zip --out D:\imp-data\13f\index.sqlite
```

The tool refuses an output path inside the repository. Point
`IMP_13F_INDEX_PATH` at the result. Two data sets (filings 2026-03-02 to
2026-08-31; 9,000 Q2 2026 and 9,081 Q1 2026 reports; 5.4 M position lines) built
in 48 s into a 361 MB file.

## Real acceptance (2026-09-28 23:56 → 2026-09-29 01:20 UTC)

Local API from this branch with `IMP_EDGAR_LIVE=1`, an SEC contact
User-Agent, `IMP_PUBLIC_RECORDS_LIVE=1`, the 13F index above, Finviz Elite
(US Equities catalog), and Moomoo OpenD (ETF and Futures catalogs, until it
stopped responding at ~00:40 UTC).

| Request | Cold / warm | Result |
|---------|-------------|--------|
| Ownership view, US Equities, 5 business days | 2.2 s / 0.01 s | `CURRENT_AS_FILED`; 1,149 filings (Form 4 1,089 · 13D 38 · 13G 22); 4,252 of 4,291 instruments have an SEC CIK |
| Congress view, US Equities, 60 days | 0.09 s (`PENDING`) / 0.02 s | background load ~44 s: 136 PTRs, 116 parsed, 20 scanned, 1 document error (isolated, `PARTIAL`); 764 transactions in window, 605 match the universe, 74 name other tickers, 85 have no ticker |
| Congress view, ETFs, 60 days | 1.6 s / 0.01 s | 24 matched rows (see ETF catalog note below) |
| Positioning view, Futures | 3.9 s / 0.01 s | 32 of 178 roots mapped to a CFTC market; `PARTIAL · SOME_ROOTS_NOT_MAPPED_TO_A_CFTC_MARKET` |
| Institutional & Whale, NVDA · AAPL · LMT · BRK-B · AMAT | 2.3–3.4 s / 0.03–0.2 s | `CURRENT_AS_FILED`; NVDA: 13D/13G, Form 4, 13F top holders of 5,956 Q2 2026 managers |
| Congress & Government, same five | 5.5–8.0 s / 0.01–1.6 s | `PUBLICATION_CURRENT`; NVDA/AMAT no award actions in 90 days; LMT, AAPL, BRK-B, MSFT with awards; LDA filings for all |

Upstream latency measured directly: USAspending 3.8 s (two searches), its
publication stamp 0.5 s, LDA 3.0 s. The 1.6 s warm outliers occur while the
House PDF loader is still parsing.

After OpenD stopped, the Futures and ETF catalogs could not load: the Positioning
and ETF Congress views answer in ~6 s with `PENDING · UNIVERSE_INDEX_LOADING`
(before the fix below they hung past 100 s).

## Visual acceptance

Checked in the in-app browser against the local API and Vite at 1920×1080,
2560×1440, and 1100×800: Congress view (100 single-line rows, 20–21 px, internal
scroll, pager "1–100 of 605", no page scroll at any size), Institutional view,
Positioning view (populated and catalog-loading states), both dock panels for
NVDA side by side (badges "Current as filed" / "Current publication", every
section and boundary present), and the select-an-instrument state after reload.
At 1100×800 with the default 300 px dock the view body is 137 px tall (the S11
News feed gets 112 px under the same dock); the dock is resizable.

The Quick Preview **Participants** tab could not be checked live: the preview
payload depends on OpenD bars, which were unavailable after 00:40 UTC. Its
behavior is covered by the UI tests below.

**Owner-workstation follow-up (2026-09-29, OpenD running).** Participants was
checked live for NVDA and MSFT. It showed OpenD 5m bars; 13D/13G, Form 4, and
13F top holders (NVDA: 5,956 Q2 2026 managers, BlackRock 1.9B shares); the 13F
"not a live position" wording; canonical House names; federal awards; and a
per-chamber note. Rapid selection NVDA → AAPL → LMT → MSFT ended with every
section owned by MSFT, with no hang and no stale payload. Both panels opened
once each (re-pressing a launcher focuses the open panel) and were resizable.
Three layout defects were found and fixed:

- The seventh preview tab overflowed the default 400 px preview. Selecting it
  scrolled the whole preview 46 px sideways and clipped every section's left
  edge. The strip now scrolls itself, like the Screener's other tab strips.
- As a scroll container in the preview's flex column, the strip then collapsed
  to 1 px. It now keeps its height and uses the Screener's thin, themed
  scrollbar.
- The participant tables' visually hidden captions were anchored outside the
  preview's scroller. They made the overflow-hidden page 293 px taller than the
  viewport, and scrolling one into view (screen-reader table navigation)
  shifted the page up with no way back. The preview now anchors its own
  descendants.

CSS contract tests in `QuickPreview.test.tsx` pin all three fixes. Checked in
the browser at 1920×1080, 2560×1440, and 1100×800 (page height equals the
viewport).

Defects found and fixed during acceptance, each with a regression test:

- congressional rows carried `member_key`, which the server's secret-leak audit
  reads as a secret-shaped key, so every Congress payload with rows returned 500
  — renamed `member_id`; the leak test now scans every S12 payload with rows;
- overall and provider states used a generic `CURRENT` — replaced by the S12
  state names; a test walks every state in every payload;
- government sources were awaited one after another (cold 6.9–11.6 s) — they
  now start together;
- the public-records throttle slept while holding a global lock, so the House
  PDF loader delayed USAspending and LDA — per-host slots, waiting outside the
  lock;
- the universe catalog loaded on the request thread, so an unreachable catalog
  hung the view — now off-request with `PENDING` / `SOURCE_ERROR`;
- changing a view filter blanked the table and removed the server-provided
  filter options while the next page loaded — the previous page stays with an
  "Updating…" notice;
- the panel header showed the raw state code — plain-language badge;
- at 1100 px a wide table scrolled the whole panel sideways — horizontal scroll
  is confined to the table's section;
- 13F change counts lacked thousands separators; loading text lowercased "CFTC".

Seen once and not reproduced in three attempts: after opening both S12 panels
within 300 ms of each other on an empty dock, only one remained open. Both stay
open in every retry, including the same sequence.

## Performance

- Universe views: cold 0.1–3.9 s (SEC daily indexes, CFTC, House index), warm
  ≤ 0.02 s. The House PTR set loads progressively in the background (~44 s for
  136 PDFs at the Clerk's pace); views are usable while it loads.
- Panels: Institutional cold 2.3–3.4 s, warm ≤ 0.2 s; Congress & Government cold
  5.5–8.0 s (bounded by USAspending and LDA), warm ≤ 0.02 s once settled.
- Caches: House index 6 h, SEC daily index 30 min (today) / 24 h (past),
  submissions 30 min, COT 3 h, USAspending 12 h, LDA 24 h, universe catalog
  10 min. Provider state is in process memory.
- 13F queries ~0.1 s against the 361 MB index.
- Bundle: initial JS 201.40 KiB gzip (budget 203 KiB; 201.42 KiB before S12).
  Lazy chunks: `IntelligenceView` 3.93 KiB, `InstitutionalPanel` 1.17 KiB,
  `PreviewParticipants` 0.99 KiB, `CongressGovPanel` 0.89 KiB gzip.

## Tests

- `tests/sec_edgar/test_s12_ownership.py` (19): daily-index grouping, subject
  role and self-submission exclusion, Form 4 and 13D/13G parsing, 13F index
  build, point-in-time selection, restatements, exits, filing window.
- `tests/market_trackers/test_s12_house_ptr.py` (15): Clerk index, PTR PDF
  parsing (joint, dependent-child, options, scanned), malformed rows, bands.
- `tests/cftc/test_s12_screener_positioning.py` (8): category mapping, derived
  net, publication time, unmapped roots.
- `tests/public_records/test_s12_public_records.py` (14): USAspending families,
  truncation, signed obligations; LDA income vs expenses; live gate, stable
  error codes, per-host pacing that never blocks other hosts.
- `tests/platform/test_screener_s12.py` (33): no new universe, panels and views
  per universe, read-only routes, gates, invalid parameters, each view and lens,
  state vocabulary, secret-leak audit over every payload, concurrent government
  sources, catalog pending/failure, progressive loader.
- `ui/src/components/screener/participants/Participants.test.tsx` (17):
  contracts and identity guards, tabs per universe, views, filters and paging
  through URL params, universe switch, not-configured and error states,
  panels, settled-selection fetching, Preview lenses, and the panel-layout
  save timer (flushed once on unmount, never fired afterwards).
- Earlier contracts updated: S5 Futures panels include `institutional`; the S7
  launcher list includes both S12 panels.

## Known limitations

- Senate eFD is not integrated (interactive terms acceptance); House only.
  *([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md): operator-import boundary; live acceptance pending the owner.)*
- 20 of 136 House PTRs in the acceptance window were scanned images; they are
  counted and linked, not parsed. *([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md): explicit `SCANNED_UNPARSED` state and
  coverage metrics; still not parsed — no approved extraction engine.)*
- Member names are shown as indexed; one member can appear under two index
  spellings (e.g. "John McGuire" and "John J Mr McGuire III", VA05).
  *([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md): canonical identity; that suffix variant merges only with the official
  registry.)*
- The 13F index is a manual local build and is not refreshed automatically;
  reports filed after the newest data set are missing until the next one.
  *([S14](SCREENER_S14_DISCLOSURE_COVERAGE.md): managed refresh lifecycle with freshness state.)*
- The daily form index carries dates only; acceptance times appear in the
  per-instrument panel, not the universe view.
- USAspending and LDA matching is by name as written by the source; parent-linked
  recipients are included and named, generic names are refused.
- The ETF universe catalog (Moomoo) includes some REITs, closed-end funds, and
  trusts (e.g. EQIX, WY, AIO); the ETF Congress view matches them because they
  are universe members. This predates S12 and is corrected at the source in
  [Screener S13](SCREENER_S13_UNIVERSE_INTEGRITY.md); the ETF views follow the
  corrected universe with no downstream special case.
- Large prints carry no participant identity; S12 links to Order Flow and never
  labels them institutional.
- Cold Congress & Government panels take 5–8 s, bounded by the government APIs.

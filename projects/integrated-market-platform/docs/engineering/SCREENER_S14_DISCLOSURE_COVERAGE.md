# Main Screener S14 — Disclosure coverage, identity & refresh automation

Status: **complete; owner-workstation live acceptance passed 2026-09-29**
(see [Owner-workstation acceptance](#owner-workstation-acceptance)).
S14 is a data-integrity continuation of
[S12](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md). It adds no universe,
view, panel, or evaluative feature, and does not touch
[S13](SCREENER_S13_UNIVERSE_INTEGRITY.md) classification.

## Objective

Remove the S12 limitations that were operational or data-integrity weaknesses:

| S12 limitation | S14 answer |
|----------------|------------|
| 13F index hand-built from ZIPs the operator picked; never refreshed | Managed lifecycle: discover → download → verify → rebuild → validate → atomic publish → rollback; freshness on every 13F surface |
| One member under several Clerk spellings | Canonical member identity beside the filed spelling, merged only on official-id or same-seat evidence |
| Scanned House PTRs counted but not represented | Document classes and parse states; "not read" is never "no transactions"; scanned-extraction boundary |
| Senate eFD not integrated | Operator access boundary (terms accepted by a person, never automated), eFD report parser, shared normalized contract |
| Disclosure timing | Point-in-time campaign across all families; one real lookahead fixed |

## Architecture

```
SEC Form 13F data-set page ──(operator/background: thirteen_f_refresh.py)──► <IMP_DATA>/13f
   sources/ (verified ZIPs + sidecars) → generations/<id>/{index.sqlite, manifest.json} → CURRENT
                                                      │ files only, no network
                                                      ▼
                    ManagedIndex (ui_api request path) → Institutional & Whale · 13F section + index status

House Clerk index + PTR PDFs ──(HousePtrLoader, S12)──► house.parse_ptr_pdf (class + parse state)
Senate eFD pages saved by the operator ──► senate.scan_import (attestation gate) → senate.parse_report
                    │                                   │
                    └──── normalized.CongressionalDisclosure (one contract) ────┘
                                     │  identity.MemberResolver (batch, evidence-based)
                                     ▼
          Congress view · Congress & Government panel · Quick Preview (compact)
```

All modules extend S12 code; no parallel system:

| Module | Role |
|--------|------|
| `sec_edgar/thirteen_f_index.py` | S12 index; S14 adds archive verification, duplicate-accession safety, provenance meta, `indexed_through` |
| `sec_edgar/thirteen_f_lifecycle.py` (new) | Store, discovery, lifecycle (check/refresh/rollback), `status()`, `ManagedIndex` |
| `tools/sec_edgar/thirteen_f_refresh.py` (new) | Operator command |
| `congressional_ptr/house.py` | S12 parser; S14 adds document classes, parse states, row labels, page refs, `ScannedPtrExtractor`, coverage metrics, ET availability |
| `congressional_ptr/identity.py` (new) | Name normalization, official registry, `MemberResolver` |
| `congressional_ptr/senate.py` (new) | eFD boundary, import scan, report parser |
| `congressional_ptr/normalized.py` (new) | `CongressionalDisclosure`, `visible_as_of`, `versions_as_of` |
| `ui_api/screener_participants.py` | S12 service; wires the above into the existing views and panels |

## 13F refresh lifecycle

### Official source and discovery

The SEC publishes the Form 13F data sets on one page,
`https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets`; there is
no machine-readable index. Discovery (`parse_listing`) admits only links to
`*_form13f.zip` on `www.sec.gov` whose file name states its filing-date window —
`01jun2026-31aug2026_form13f.zip` (current naming) or `2023q4_form13f.zip`
(legacy quarterly). A name that does not parse is skipped, never guessed. The
fetcher is injectable; the default uses the S12 SEC transport (declared
`SEC_USER_AGENT`, process-wide Fair Access throttle) and streams ZIPs to disk
with a size check.

`--check` compares the newest *N* published data sets (default 2: the current and
prior filing windows S12's quarter-over-quarter comparison needs) with the active
generation's manifest and records `last_check.json`.

### External storage

```
<IMP_DATA>/13f/                        (IMP_13F_DATA_ROOT; any OS, no drive letters)
  sources/<name>_form13f.zip           verified data set
  sources/<name>_form13f.zip.json      url, sha256, bytes, coverage, downloaded_at
  generations/<id>/index.sqlite        immutable generation
  generations/<id>/manifest.json
  generations/<id>.building/           candidate (never read by the Screener)
  CURRENT                              {"generation", "manifest_sha256", "previous", "published_at"}
  refresh.lock · last_check.json · last_refresh.json
```

The command refuses a root inside the repository. Nothing under the root is
committed.

### Source integrity

- Download to `*.part`, then `verify_archive`: readable ZIP, the three required
  tables (`SUBMISSION`, `COVERPAGE`, `INFOTABLE`), required columns. Row-level
  CRCs are verified as the build streams each table; a corrupt member fails the
  candidate, never the active index.
- The sidecar records the file's SHA-256. On reuse the file is re-hashed; a
  mismatch quarantines it (`*.quarantine`) and fails the refresh with
  `THIRTEEN_F_SOURCE_HASH_MISMATCH`; the next refresh downloads it again.
- An accession that appears in two data sets with identical submission facts is
  counted once (its lines are never summed twice); conflicting facts fail with
  `THIRTEEN_F_DUPLICATE_ACCESSION_CONFLICT`. (S12's build silently double-summed
  such a repeat.)

### Build strategy: deterministic full rebuild

Each candidate is a full rebuild of the chosen source set with the unchanged S12
`build_index`. Incremental mutation was rejected: a rebuild cannot inherit a
half-applied increment, the source set fully determines the result, and it is
fast enough (S12: 5.4 M lines in 48 s; S14 cloud measurement below).

### Manifest

`manifest.json` per generation: `schema_version`, `generation`, `generated_at`,
`index_schema`, `tool_version`, `parent_generation`, `source_datasets[]` (name,
url, sha256, bytes, coverage start/end, downloaded_at), `source_sha256`,
`coverage_start`, `coverage_end`, `filing_date_min`/`max`, `filing_count`,
`submission_count`, `position_count`, `line_count`, `duplicate_accessions`,
`index_bytes`, `index_sha256`, `smoke`, `timings`. The index's own `meta` table
also carries the generation id and coverage, so an index file is identifiable
without its folder name.

### Validation, atomic publish, rollback

1. Candidate built in `generations/<id>.building/`.
2. Validation: `PRAGMA quick_check`; the index opens with the Screener's reader;
   its meta generation matches the manifest; a smoke query of the most-held
   CUSIP just after the newest window returns holders.
3. `os.replace` renames the candidate to `generations/<id>`, then `CURRENT` is
   replaced atomically (`CURRENT.tmp` → `os.replace`; atomic on POSIX and
   Windows). Readers see the old or the new generation, never a mix.
4. Any failure before step 3 leaves `CURRENT` untouched; leftovers (`*.part`,
   `*.building`, `CURRENT.tmp`) are removed at the start and end of every refresh.
5. `--rollback` re-points `CURRENT` at the parent after a deep hash check.
6. Retention keeps three generations and never prunes the active one or its
   parent. On Windows an index still open by a running API is skipped and pruned
   next time.

### Concurrency and crash safety

One refresh at a time: `refresh.lock` is created with `O_CREAT | O_EXCL`. A
second refresh returns `REFRESH_ALREADY_RUNNING` and leaves the owner's lock
alone. A lock older than six hours is treated as left by a dead process and
reclaimed (age is the only portable liveness signal: `os.kill(pid, 0)`
terminates processes on Windows). Lock age is always wall-clock time, and a lock
that is still being written (empty or partial JSON) is dated by its mtime — a
race found by the S14 concurrency test, where a second refresher read the
owner's half-written lock as stale and deleted it. Tests simulate a crash at download, build,
validate, before the swap, and after the candidate completes: the active index
stays valid each time and the next refresh recovers.

### Freshness and states

`status()` reads files only. `refresh_state`:

| State | Meaning |
|-------|---------|
| `NOT_CONFIGURED` | no data root, or no generation built yet |
| `CURRENT_AS_FILED` | the index holds the newest data sets the SEC has published (as of the last check) |
| `REFRESH_AVAILABLE` | a newer published data set is not indexed yet |
| `REFRESHING` | a refresh holds the lock; the previous generation is served |
| `UNCHECKED` | never compared with the SEC page |
| `SOURCE_ERROR` | the last check could not reach the SEC page; the index is still served |
| `INDEX_INVALID` | the active generation's files do not match its manifest |
| `UNMANAGED` | an S12 hand-built index via `IMP_13F_INDEX_PATH` |

Plus `generation`, `generated_at`, `age_days`, `indexed_through`,
`latest_source_filing_date`, `latest_indexed_dataset`, `source_dataset_count`,
`is_current_for_available_datasets`, `missing_datasets`, `last_refresh_error`.

The refresh state is separate from the data state of the 13F section
(`CURRENT_AS_FILED` / `PARTIAL · FILING_WINDOW_OPEN` / …): old-but-newest-published
data is never presented as a failure, and nothing is labelled live.

### Request path

`participant_service()` uses `IMP_13F_DATA_ROOT` when set (`ManagedIndex`), else
the S12 `IMP_13F_INDEX_PATH` (served as `UNMANAGED`). `ManagedIndex` re-reads the
pointer at most every 30 s, opens a newly published generation, closes the old
one after in-flight queries finish, and retries once if a generation is swapped
mid-request. It never discovers, downloads, or locks.

## 13F point in time

- `period` (quarter end), `filing_date`, and `available_at` (start of the next
  UTC day; EDGAR dates a filing accepted after 17:30 ET to the next business day,
  so every filing dated D is public before D+1 00:00 UTC) are kept per holder.
- Queries select, per manager and period, the newest base report and
  NEW HOLDINGS amendments **filed by the cutoff**; every report is stored, so a
  refresh that adds a later restatement never changes an earlier view.
- `EXITED` requires the manager's own filing for the current period. S14 adds a
  coverage guard: if the index's data sets end before the quarter's 45-day
  deadline, the section is `PARTIAL · INDEX_ENDS_BEFORE_FILING_DEADLINE` rather
  than `CURRENT_AS_FILED`.

## Congressional member identity

### Official identifiers

Neither the House Clerk index nor Senate eFD carries a Bioguide id; the Clerk
index gives name parts and seat (`StateDst`), eFD a filer name. Stable ids
therefore come from an **operator-supplied registry** keyed by official Bioguide
ids with dated terms, in the `congress-legislators` JSON layout
(`IMP_CONGRESS_LEGISLATORS_PATH`, several files separated by the OS path
separator). Entries without a Bioguide-shaped id are ignored.

### Resolution (`MemberResolver`, batch)

| Resolution | Evidence | Canonical id |
|------------|----------|--------------|
| `OFFICIAL_ID` | House: exactly one registry member held that seat on the filing date **and** the surname agrees. Senate: exactly one senator serving on that date (in the stated state, if any) has the surname; if two share it, the given name (or nickname) must also agree | `BIOGUIDE:<id>` |
| `SEAT_AND_NAME` | House, no registry: same seat, same given name, same surname, same generational suffix after removing honorifics and middle names/initials | `HOUSE-SEAT:<seat>:<SURNAME>:<GIVEN>[:<SUFFIX>]` |
| `AMBIGUOUS` | conflicting middle initials in one seat, or several registry candidates | `SOURCE:<source identity>` (kept apart) |
| `UNRESOLVED` | no official or seat evidence (every Senate identity without a registry) | `SOURCE:<source identity>` |

Rules that prevent speculative merges:

- A suffix present in one spelling and absent in another is **not** merged
  without the registry (a Jr. can succeed a parent in the same seat); both carry
  the note `SUFFIX_VARIANT_IN_SAME_SEAT_UNVERIFIED`.
- Nicknames ("Rich" / "Richard") are merged only through the registry.
- Same name in different seats, different chambers without a registry, or
  outside any registry term: never merged.
- Registry terms make resolution point-in-time safe: a district change or a
  House→Senate move keeps one Bioguide id; a same-named successor resolves to a
  different one by date.

### Provenance and UI

Every row keeps `member.source_name` (the spelling as filed), `member_id` (S12's
source id; S12 filter links still work), and adds `canonical_member_id`,
`canonical_name`, `resolution`, `basis`, `aliases`, `official_ids`, `notes`.
`member.name` is the canonical display name only when the resolution is
`OFFICIAL_ID` or `SEAT_AND_NAME`. The member filter lists one entry per canonical
member with its `filed_as` spellings; disclosure rows are never collapsed.

## House PTR coverage

### Document classes and parse states

| Document class | Meaning |
|----------------|---------|
| `TEXT_PDF` | every page has a text layer |
| `SCANNED_PDF` | no text layer; image pages |
| `MIXED` | some pages have text, some are images only |
| `MALFORMED` | not a PDF, unreadable streams, or neither text nor images |
| `UNSUPPORTED` | encryption other than the generator's RC4, or over 8 MB |

| Parse state | Meaning |
|-------------|---------|
| `PARSED` | every row read |
| `PARTIALLY_PARSED` | rows read, but some rows unrecognized, a critical field unparsed (band, transaction date, asset), image-only pages, or low-confidence extracted rows withheld |
| `NO_TRANSACTIONS` | a readable transaction table with no row in it |
| `SCANNED_UNPARSED` | scanned; no approved extraction engine (or extraction failed / below confidence) |
| `PARSE_FAILED` | table not found, rows unrecognized, malformed, or unsupported |

S12's coarse `state` (`PARSED` / `TRANSACTIONS_NOT_MACHINE_READABLE` /
`PARSE_ERROR`) is still emitted for existing consumers.

### Machine-readable hardening

- Per-row labels are kept verbatim: Filing Status (`New`, `Amended`),
  Description (e.g. option strike and expiry), Subholding Of (account).
- Each row records its source page.
- Invalid transaction or notification dates are flagged
  (`TRANSACTION_DATE_UNPARSED`), never guessed; a notification before the trade is
  flagged.
- A row-shaped line with an unknown transaction code is counted as unrecognized
  and no longer lets its asset text bleed into the next row (S12 defect found by
  the S14 synthetic fixtures).
- Owners (self, spouse, joint, dependent child), options (`[OP]`), wrapped asset
  names, page-break continuations, open-ended and malformed bands, and missing
  tickers are covered by real and synthetic fixtures.
- Amended rows: the House form marks a row amended but does not name the report
  it amends, so `amendment.linked_to` is `null` — no linkage is invented.

### Scanned documents

No OCR engine exists in the repository and none was added (a heavyweight cloud
OCR dependency is out of policy for financial disclosure facts).
`ScannedPtrExtractor` is the boundary: an engine returns rows with page, raw
text, optional bounding box, per-field text, and confidence. Rows below 0.98
confidence are withheld; admitted rows are `evidence_class: EXTRACTED` (never
`OBSERVED`) with provenance in `extraction`. The default extractor has no engine,
so scans stay `SCANNED_UNPARSED`.

### Coverage metrics

`coverage.house` (and the `house_ptr` provider's `coverage`): `documents_total`,
`documents_read`, `machine_readable`, `scanned`, `mixed`, `malformed`,
`unsupported`, `parsed`, `partially_parsed`, `no_transactions`,
`scanned_unparsed`, `failed`, `loading`, `document_errors`, `transaction_count`,
`extracted_transactions`, `withheld_rows`, `unrecognized_rows`. These are
coverage counts, not quality scores.

## Senate eFD

### Official access findings (terms boundary)

- Senate financial disclosures are published at `efdsearch.senate.gov`. Search
  and report pages are served only after a person accepts, interactively, a
  statement of the statutory restrictions on obtaining and using the reports
  (5 U.S.C. § 13107(c): no unlawful purpose, no commercial purpose other than
  news-media dissemination, no credit rating, no solicitation).
- There is no documented public API or bulk file.
- Automating the acceptance, or replaying its session cookie, would automate
  around an access control. IMP does neither, stores no cookie or token, and
  never contacts eFD.
- The cloud environment cannot reach eFD at all (egress policy); no live page
  was fetched for S14.
- Whether IMP's intended use is within those restrictions is the owner's
  decision to make when accepting the terms; S14 does not make it.

### Provider boundary

The legitimate path implemented: the **operator** accepts the terms in their own
browser, saves the official report pages, and puts them in
`IMP_SENATE_EFD_IMPORT_DIR` with an `ACCESS_ATTESTATION.json`
(`accepted_by`, `accepted_at`, optional `statement`) recording that they accepted
the terms. An optional `<file>.json` sidecar may give `source_url` and
`retrieved_at`.

| Provider state | When |
|----------------|------|
| `TERMS_ACCEPTANCE_REQUIRED` | no import directory configured (reason `SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE`), or no valid attestation (`OPERATOR_ATTESTATION_MISSING`) — no file is read |
| `NOT_CONFIGURED` | the configured directory does not exist |
| `READY` | attested import read; every report parsed or explicitly classified |
| `PARTIAL` | some reports failed |
| `SOURCE_ERROR` | no report could be read |

The House and Senate providers are independent: a House failure with a Senate
import shows the Senate rows (`PARTIAL · HOUSE_SOURCE_ERROR`), and vice versa.

### Parser

`senate.parse_report` locates the transaction table **by header text** (`#`,
Transaction Date, Owner, Ticker, Asset Name, Asset Type, Type, Amount, Comment;
order-independent, Comment optional), reads the filer ("The Honorable …" and its
parenthetical), the filed timestamp ("Filed MM/DD/YYYY @ h:mm AM", Eastern), the
report-for date, and an "Amendment n" marker in the title. Report ids come from
the eFD URL (`/search/view/ptr/<id>/` or `/paper/<id>/`) in the sidecar, the
browser's "saved from url" comment, or a link. Paper filings are
`SCANNED_UNPARSED`. Unknown transaction types, bad bands, and missing tables fail
per row or per report with a reason. Two saved copies of the same report count
once; two different contents under one report id fail closed
(`DUPLICATE_REPORT_CONFLICT`).

**Fixtures are synthetic** (`tests/fixtures/congressional_disclosure/senate_efd/`):
authored to mirror the eFD page layout with fictitious names and ids. The
"(Amendment 1)" title form is an assumption of the fixture. They prove the parser
and boundary, not live access.

## Normalized contract

`normalized.CongressionalDisclosure` (contract `congressional_disclosure/1.0.0`)
for both chambers: id, chamber, source provider/document/url, row index, source
identity, owner, asset description, disclosed ticker, asset type (code and source
text), transaction type (normalized and code), transaction date, notification
date (House only), filing date, filed time (Senate), `available_at` with basis and
`date_quality`, `retrieved_at`, `imp_known_at`, amount **band** (never a point),
parse state, evidence class, quality flags, amendment, version key, and
chamber-specific `source_specific` fields. Only genuinely common semantics are
normalized.

## Point in time

| Clock | House | Senate |
|-------|-------|--------|
| transaction date | as printed | as printed |
| notification date | as printed | — |
| filing | date (Clerk, Eastern) | timestamp to the minute (Eastern) |
| `available_at` | end of the Eastern filing day (`DATE_ONLY`) | the filed timestamp (`SOURCE_TIMESTAMP_MINUTE`); end of the Eastern day if only a date |
| `retrieved_at` | IMP's first download | operator sidecar, else file time |
| `imp_known_at` | later of `available_at` and `retrieved_at` | same |

**Lookahead fixed.** S12 bounded a House filing date at the end of the *UTC* day,
four to five hours before the end of the Eastern day the Clerk's date refers to:
a filing made in the evening, Eastern, looked public before it was filed. S14
uses the end of the Eastern day.

**Retrieval ≠ publication.** S12 moved House availability to IMP's first
retrieval when that was later. S14 keeps publication availability and records
retrieval separately (`imp_known_at`); `visible_as_of(..., clock="imp")` answers
"what could IMP itself have known".

**Amendments.** Each version is its own record with its own availability;
`versions_as_of` reports, per linked Senate report (filer + report-for date), the
version current at a cutoff and the superseded ones. The earlier public record is
never erased. House amendments are flagged per row and not linked.

SEC ownership filings (Form 4, 13D/13G) keep S12's clocks: availability is the
EDGAR acceptance time, else the end of the filing date; the event or transaction
date is never used.

## UI changes (small)

- **Institutional & Whale → 13F section:** "13F index: data sets indexed through
  2026-08-31 (2 data sets) · generated … · refresh: current for published SEC data
  sets / update available / refreshing / SEC list unavailable / index invalid".
  The 13F provider chip shows "data sets through …".
- **Congress & Government → congressional section:** per-chamber source coverage,
  e.g. "House · Current publication · 116 parsed · 20 scanned/unparsed" and
  "Senate · Terms acceptance required" (actual counts only).
- **Congress view:** canonical member names in the table and member filter
  (filed spellings on hover), chamber coverage line under the S12 coverage line;
  Senate rows show "(Senate)" for the seat.
- **Quick Preview:** one line for 13F ("indexed through … · …") and, only when a
  chamber is not available, a one-line chamber note. No new tab.
- New plain-language state texts: Terms acceptance required, Imported, Index
  invalid, Refreshing, Update available.

No ranking, scoring, party, or performance field was added; the S12 neutrality
note now also says names are merged only on official-id or same-seat evidence.

## Configuration

| Variable | Purpose |
|----------|---------|
| `IMP_13F_DATA_ROOT` | managed 13F root (preferred); served by `ManagedIndex` |
| `IMP_13F_INDEX_PATH` | S12 hand-built index (still supported; `UNMANAGED`) |
| `SEC_USER_AGENT` | required for `--check` / `--refresh` (name + contact email) |
| `IMP_CONGRESS_LEGISLATORS_PATH` | optional official-id registry file(s) |
| `IMP_SENATE_EFD_IMPORT_DIR` | optional attested Senate import directory |

### Operator command

```
python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --status
python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --check
python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --refresh [--dry-run] [--force] [--datasets 2]
python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --rollback
python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --generations
```

Offline: `--listing-file <saved SEC page>` and `--import-zip <official ZIP>`
(repeatable) run the same verification without network. The tool uses the
interpreter that runs it (use the project Python) and has no PowerShell
dependency.

## Performance (cloud, synthetic data)

| Operation | Result |
|-----------|--------|
| Candidate build, 2 data sets, 1.0 M lines → 995 k positions (48 MB) | 5.6 s (≈ 5.4 M lines ⇒ ~30 s; S12 measured 48 s on the workstation) |
| Validation (quick_check + smoke query) | 0.16 s |
| Pointer swap | 0.2 ms |
| `status()` | 0.15 ms |
| Discovery parse / `--check` without network | < 1 ms |
| `ManagedIndex` query (first / warm) | 2 ms / 0.7 ms |
| Identity resolution, 2,000 source identities | 5.9 ms |
| House PTR parse, 8-page / 78-row PDF | 0.26 s (background loader, as S12) |

The request path makes no network call for 13F, Senate, or identity; the Senate
import is rescanned at most every 5 minutes.

## Tests

| Suite | Tests |
|-------|-------|
| `tests/sec_edgar/test_s14_thirteen_f_lifecycle.py` | 37 — connections closed before publish, discovery, archive integrity, duplicate accessions, first build + manifest, no-op, one/two new data sets, dry run, corrupt ZIP, missing table, conflict, build failure, smoke failure, empty index, hash mismatch + recovery, discovery failure, crash at every stage, dead-process leftovers, atomic pointer, rollback (and refused rollback), stale manifest, pruning, half-written lock, lock contention, concurrent refreshes, PIT after refresh, exits during the filing window, coverage-short index, CLI |
| `tests/market_trackers/test_s14_house_ptr_coverage.py` | 20 — real text/scanned fixtures, page refs, row labels, metrics; synthetic PDFs for empty table, missing table, unrecognized rows, partial parse, page-break continuation, missing ticker, amended row + option description, invalid dates, mixed pages, malformed/unsupported; scanned extractor admission, withholding, failure |
| `tests/market_trackers/test_s14_congress_identity.py` | 16 — names, seat evidence, honorifics, suffix variants, conflicting initials, same name/different seat, nicknames, unknown, Senate without registry, registry ids, successor in same seat, vacancy, chamber transition, Senate ambiguity, surname guard, env loading |
| `tests/market_trackers/test_s14_senate_efd.py` | 16 — parser, filer courtesy titles, owners/types/bands, amendment, paper, malformed, unknown type/bad band, header-driven columns, no-transactions, attestation gate, import states, duplicates/conflicts, sidecar retrieval, normalized contract, versions |
| `tests/platform/test_screener_s14.py` | 15 — Senate on the Congress view and panel, independent source failure, partial import, unattested directory, identity filter dedupe, filed-name provenance, House coverage metrics, managed 13F freshness, refresh-available, refreshing + switch, invalid index, no network on the request path, neutrality |
| `tests/platform/test_screener_s14_pit.py` | 13 — House scenario A, ET bound, retrieval clock, House amended row, Senate minute precision, Senate amendment, 13F scenario B, 13F restatement, Form 4/13D acceptance clocks, cross-family invariants |
| `ui/…/participants/ParticipantsS14.test.tsx` | 7 — 13F status line (full/compact/invalid), chamber coverage, compact chamber note, canonical name + filed-as provenance, S14 schema |

S12 tests updated only where S14 deliberately supersedes S12 behavior: the
Senate provider state (`TERMS_ACCEPTANCE_REQUIRED`), House `available_at` (end
of the Eastern filing day; retrieval kept separately), member filter ids
(canonical, with S12 ids still accepted), and the narrowly extended state
vocabulary. Validation results are in the PR and the [work log](WORK_LOG.md).

## Cloud acceptance

`SOURCE_UNAVAILABLE_IN_CLOUD`: the container's egress policy denies
`www.sec.gov`, `disclosures-clerk.house.gov`, `efdsearch.senate.gov`, and
Bioguide hosts (CONNECT 403, 2026-09-29). No live data set was discovered or
downloaded, no live House document was parsed, and no Senate page was seen.
Everything above was proven with deterministic fixtures.

## Owner-workstation acceptance

Run 2026-09-29, 10:51–13:15 UTC, on the owner workstation (Windows 11,
Python 3.11.15, Moomoo OpenD 10.10.7008, Finviz Elite). The data sources were
the live SEC, House Clerk, USAspending, LDA, and CFTC, plus three real eFD
reports that the owner saved after accepting the terms personally. The 13F
data, registry file, and Senate pages live outside the repository
(`C:\Users\adame\imp-data`); none is committed. S13's gate is recorded
separately ([S13](SCREENER_S13_UNIVERSE_INTEGRITY.md#acceptance)).

### 13F lifecycle (live SEC)

| Step | Result |
|------|--------|
| `--status` on an empty root | `NOT_CONFIGURED · THIRTEEN_F_INDEX_NOT_BUILT` |
| `--check` | 0.56 s. The SEC page lists 54 data sets; the newest is `01jun2026-31aug2026_form13f.zip` (coverage end 2026-08-31). The wanted two were both missing; nothing was mutated. |
| `--refresh` | **`PUBLISHED`** in 52.3 s. Downloads: 99.4 MB + 100.7 MB (≈7 s). Build 45.1 s, validation 1.0 s, pointer swap under 1 ms. |
| Generation | 19,616 13F-HR filings, 23,613 submissions, 7,653,159 lines → 5,401,302 positions, 0 duplicate accessions, 361,484,288-byte index. The smoke query found CUSIP 594918104 (MSFT) with 6,212 Q2 holders, `CURRENT_AS_FILED`. |
| `--status` | 0.24 s: **`CURRENT_AS_FILED`**, indexed through 2026-08-31, latest source filing 2026-08-31, current for the published data sets |
| `--refresh` again | `NO_CHANGE` (0.44 s) |
| `--rollback` with no parent | refused: `NO_PARENT_GENERATION`; `CURRENT` unchanged |
| `--refresh --force`, then `--rollback`, then `--refresh --force` | Generation 2 was built from the cached, hash-verified sources (53.6 s; parent = generation 1). The rollback re-pointed `CURRENT` to generation 1 after a deep hash check (0.47 s); status stayed `CURRENT_AS_FILED`. Generation 3 restored the newest data (parent = generation 1). All three generations show 5,401,302 positions and the same source hash. The index file hashes differ only because each index carries its own generation id. |

The first real refresh would have failed on Windows. Running the S14 suites on
the workstation showed every publish failing with `WinError 32`: the smoke
validator opened the candidate index through `sqlite3`'s context manager, which
commits but does not close, and the open handle blocked the
`.building` → generation rename. Linux CI cannot see that. Fixed with
`contextlib.closing` and a platform-independent test that every connection is
closed before publish (`9464f62d`).

**Request path** (API started with `IMP_13F_DATA_ROOT`): NVDA Institutional &
Whale shows "13F data sets indexed through 2026-08-31 · current for published
SEC data sets", quarter end 2026-06-30 compared with 2026-03-31, 5,956 managers,
and top holders BlackRock 1.9B, Vanguard Capital Management 1.5B, and FMR 1B.
It says "A quarter-end holding filed weeks later is not a live position".
Nothing is labeled live.

**Point in time on real filings.** Corient Private Wealth's Q2 2026 NVDA report
(filed 2026-08-12, 10,497,476 shares) was restated twice: 10,215,688 shares
(filed 08-17) and 9,069,030 shares (filed 08-27). Querying all holders:

| Cutoff (UTC) | Corient shares shown | NVDA holders |
|--------------|---------------------|--------------|
| 2026-08-17 23:59:59 | 10,497,476 (filed 08-12) | 5,840 |
| 2026-08-18 00:00:01 | 10,215,688 (filed 08-17) | 5,891 |
| 2026-08-27 23:59:59 | 10,215,688 | 5,951 |
| 2026-08-28 00:00:01 | 9,069,030 (filed 08-27) | 5,955 |

Each restatement appears only once it is public. The holder count grows only as
filings become available, so there is no lookahead. Full-holder queries took
about 110 ms.

### House (live Clerk)

135 PTR filings (load 42 s): 116 machine-readable and 19 scanned. Parse states:
114 `PARSED`, 2 `PARTIALLY_PARSED` (`SOME_ROW_FIELDS_UNPARSED`), and
19 `SCANNED_UNPARSED` (`NO_TEXT_LAYER_SCANNED_FILING`). None was `PARSE_FAILED`
or `NO_TRANSACTIONS`, there were no document errors, and there were 1,045
transactions. No scan is presented as having no transactions.

**Identity**, with the official registry (`congress-legislators`
`legislators-current.json`, 539 members): 843 rows resolved `OFFICIAL_ID` and
202 `SEAT_AND_NAME`. The 90-day member filter has 43 canonical entries, and
every merge checked out:

- "John J Mr McGuire III" and "John McGuire" → `BIOGUIDE:M001239` (VA-05).
- "Richard W. Allen" → Rick W. Allen; "Daniel Crenshaw" → Dan Crenshaw.
- "Scott Scott Franklin" → Scott Franklin; "Thomas H. Kean Jr" → Thomas H. Kean, Jr.

Two members kept the no-registry seat identity rather than an official id:
April McClain Delaney (MD-06; the compound surname does not match the parsed
surname) and Richard McCormick (the index gives GA-06; the registry's current
term is GA-07). Nothing was merged incorrectly. Filed spellings stay in
`member.source_name` and in the "Filed as …" hover.

**Clocks** (Kevin Hern, doc 20035491): transaction 2026-08-27, notification
09-15, filed 2026-09-25, `available_at` 2026-09-26T03:59:59Z (end of the
Eastern filing day), `retrieved_at`/`imp_known_at` 2026-09-29 (kept separate).
Amounts are bands with `exact_value_disclosed: false`.

### Senate (real eFD, owner operator step)

The owner accepted the eFD terms in their own browser (attestation:
`accepted_by` Adam Eddahmouni, `accepted_at` about 2026-09-29 09:03 ET) and
saved three electronic PTR pages. IMP never contacted eFD.

| Report | Filer as printed | Filed (ET) | Result |
|--------|------------------|------------|--------|
| `05f5d46b…` | The Honorable Lamar Alexander (Former Senator) | 06/27/2017 7:28 PM | `PARSED`, 10 spouse municipal-bond sales (`Sale (Full)`); identity `UNRESOLVED` (not in the current-legislators registry) |
| `9e2ff733…` | The Honorable Richard Blumenthal | 09/28/2026 9:27 AM | `PARSED`, 33 spouse transactions (24 purchases, 9 partial sales), asset type `Other`, no tickers; `BIOGUIDE:B001277` |
| `0a93a20c…` | **Mr.** James Conley Justice **II** (Justice II, James Conley) | 09/28/2026 2:13 PM | `PARSED` after the fix below: 1 self `Sale (Partial)` of non-public stock, band **Over $50,000,000** (open-ended, no point value); `BIOGUIDE:J000312` |

Import: `READY`, 3 of 3 parsed, 44 transactions, no duplicates or conflicts,
13 ms. Filed times convert correctly across DST (EDT). `available_at` is the
filed minute (`SOURCE_TIMESTAMP_MINUTE`). Rows are invisible one minute before
it on the publication clock and invisible on IMP's own clock until retrieval.
Senate rows carry the House contract's common fields, and Senate-only fields
are in `source_specific`.

**Defect found by the real pages.** The parser located the filer only by
"The Honorable …". eFD printed a sitting senator as "Mr. James Conley Justice II",
and that report failed `PARSE_FAILED · FILER_NOT_FOUND`. The import stayed
`PARTIAL · SOME_REPORTS_FAILED`, never zero transactions. The filer now comes
from the heading eFD marks `class="filedReport"`, with standard courtesy titles
removed and the old match kept as the fallback (`2a74bc76`). The test uses a
synthetic variant of the fixture: courtesy titles, a multi-line filer with a
suffix, an open-ended band, and a page saved without the class.

None of the 44 Senate transactions carries a ticker, so none matches a
Screener universe; they count as "no ticker" in the Congress coverage. The
provider shows `READY`; the chamber lines read "House · Current publication · 114
parsed · 2 partly parsed · 19 scanned/unparsed" and "Senate · Imported".

### Other live checks

- **Participants preview** (OpenD running): passed for NVDA and MSFT, including
  rapid selection. See [S12](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md#visual-acceptance)
  for the three preview layout fixes.
- **Government:** LMT, AAPL, and MSFT have USAspending award actions
  (`PUBLICATION_CURRENT`); NVDA shows `NO_DISCLOSURES · NO_ACTIONS_IN_WINDOW`
  from a healthy source. LDA returned 12 filings each.
- **Futures positioning:** 32 of 178 roots are mapped to a CFTC market
  (`PARTIAL · SOME_ROOTS_NOT_MAPPED_TO_A_CFTC_MARKET`). CFTC is
  `PUBLICATION_CURRENT` (165 items, released 2026-09-25 19:30 UTC). No mapping
  was added.
- **Controlled source failure:** a separate API with `IMP_PUBLIC_RECORDS_LIVE`
  off reported `LIVE_DISABLED · IMP_PUBLIC_RECORDS_LIVE_NOT_SET` for House,
  awards, and lobbying, never `NO_DISCLOSURES`.
- **Visual:** the layout was checked at 1920×1080, 2560×1440, and 1100×800; the
  page height equals the viewport.

### Local timings

| Operation | Time |
|-----------|------|
| 13F `--check` / `--status` / no-op refresh | 0.56 s / 0.24 s / 0.44 s |
| 13F refresh (2 data sets, download + build + validate) | 52.3 s (build 45.1–53.6 s) |
| 13F rollback | 0.47 s |
| 13F all-holder query (NVDA) | ≈110 ms |
| House load (135 PDFs, background) | 42 s |
| Ownership view, 5 days, cold | 2.1 s |
| Futures positioning, cold | 2.7 s |
| Congress & Government panel, warm | 0.1 s |
| Senate import scan (3 reports) | 13 ms |

## Limitations

- Senate eFD needs the owner to accept the terms and save report pages; IMP
  never fetches them. The parser has been checked on three real reports
  (2017 and 2026); other layouts still fail closed per report.
- The Congress coverage sentence starts from the House filing count, but its
  "have no ticker" figure also includes Senate transactions (the chamber lines
  below it are separate and correct).
- Scanned House and paper Senate filings remain `SCANNED_UNPARSED`; no extraction
  engine is approved.
- Official ids need an operator-supplied registry; without one, only same-seat
  House spellings merge, and Senate identities stay `UNRESOLVED`.
- House amended rows cannot be linked to the report they amend.
- 13F discovery depends on the SEC page's link names; an unrecognised naming
  scheme yields `SEC_LISTING_HAS_NO_DATASETS` (fails closed; the index is kept).
- The 13F build figures in [Performance](#performance-cloud-synthetic-data)
  are cloud and synthetic; the real-size figures are in
  [Local timings](#local-timings).

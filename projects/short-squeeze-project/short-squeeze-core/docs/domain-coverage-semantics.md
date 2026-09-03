# Domain Coverage Semantics

`squeeze_core.readiness.coverage.classify_domain_coverage` classifies one
`squeeze_core.evidence.CoverageDomain` against an already-built
`PointInTimeEvidenceBundle` into a `DomainCoverageState`:
`PRESENT | MISSING | UNAVAILABLE | CONFLICTED | CANCELLED | PARTIAL | UNKNOWN`.

## Precedence

Checked in this order; the first match wins:

1. **`UNKNOWN`** — the bundle has no `SourceCoverage` entry for the domain at all. This
   happens when the evidence-bundle policy that built the bundle never activated the domain:
   `PointInTimeEvidencePolicy.include_<domain>_domain` was left `False` *and* no observation of
   that domain's `EventType` was in the raw input list (`squeeze_core.evidence.builder` activates
   a domain if either condition holds). Phase 2D cannot tell "missing" from "never checked"
   here, so it reports the honest answer.
2. **`CANCELLED`** — the domain has at least one point-in-time-eligible observation, and *every*
   one of them carries a lifecycle-cancellation marker in
   `Observation.provenance.provider_metadata` (see the field table below). A domain with one
   active record and one older cancellation is `PRESENT`, not `CANCELLED`.
3. **`CONFLICTED`** — `SourceCoverage.state is CoverageState.CONFLICTED`, or any
   `EvidenceConflict` in the bundle (excluding `TEMPORAL_DIFFERENCE`-classified entries, which
   are not real conflicts) names an observation belonging to this domain.
4. **`PARTIAL`** — `SourceCoverage.state is CoverageState.PARTIAL` (Phase 1 already flags this
   for in-progress bars and SEC/halt records with partial metadata).
5. **`UNAVAILABLE`** — `SourceCoverage.state is CoverageState.MISSING`, but either (a) the
   bundle's `diagnostics` contain a domain-tagged entry whose code names a not-yet-published/
   not-yet-received/excluded-after-`as_of`/future-event condition (evidence existed but was
   point-in-time ineligible), or (b) the domain's eligible observations all carry
   `quality.state in {UNAVAILABLE, INVALID}` (a record shell whose value isn't usable).
6. **`MISSING`** — `SourceCoverage.state is CoverageState.MISSING` and nothing above fired: no
   evidence, eligible or excluded, exists for this domain at all.
7. **`PRESENT`** — everything else, including Phase 1's `STALE`/`DELAYED`/`UNKNOWN_FRESHNESS`
   coverage states. Freshness is reported separately, as an age fact
   (`docs/evidence-age-alignment-semantics.md`), never folded into presence.

Note `quality.state is MISSING` on an individual short-interest observation is **not** used as
an UNAVAILABLE signal: Phase 2C established that a known short-interest value can carry
`MISSING` quality purely because its exact publication time is uncertain, while the actual
`payload.short_shares` field is populated. Using `quality.state` broadly here would regress that
distinction, so only `UNAVAILABLE`/`INVALID` (never `MISSING`) drive the fallback UNAVAILABLE
check.

## Cancellation-detection field table

| Domain | Metadata key | Cancelled values |
|---|---|---|
| `PUBLISHED_SHORT_INTEREST` | `revision_status` | `CANCELLED` |
| `SEC_FILINGS` | `filing_status` | `CANCELLED` |
| `TRADING_HALTS` | `revision_status` | `CANCELLED` |
| `NEWS` | `status` | `WITHDRAWN`, `DELETED` |
| `MARKET_BARS` | `status` | `CANCELLED` |
| `TRADES`, `QUOTES` | `status` | `CANCELLED`, `DELETED` |
| `BORROW_FEE`, `BORROW_AVAILABILITY`, `CANDIDATE_SNAPSHOT` | — | no lifecycle concept; never `CANCELLED` |

An absent metadata key is always treated as "not cancelled," never as an error.

## `DomainCoverageSnapshot`

`build_domain_coverage_snapshot(bundle, requested_domains)` classifies every domain in
`requested_domains`, buckets them into the seven state lists, and produces one
`DomainCoverageEntry` per domain (state, observation IDs, conflict IDs, diagnostic codes). No
weighted score or coverage grade is computed; a caller wanting "N of M required domains present"
can count `len(present_domains)` against `len(requested_domains)` themselves.

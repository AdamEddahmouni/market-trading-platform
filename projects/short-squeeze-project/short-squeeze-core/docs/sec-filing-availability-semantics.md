# SEC Filing Availability Semantics

| Concept | Meaning | Point-in-time role |
|---|---|---|
| Period of report | Business/reporting period described | Reporting-period age only |
| Filed value | Filing submission/status metadata | Objective metadata; not sufficient availability |
| SEC acceptance | Time accepted by SEC | Public boundary when exact and no later explicit publication exists |
| Publication | Explicit provider public-availability time | Preferred public boundary |
| Received | Time the local system obtained metadata | Strict local-availability boundary |
| Effective | Earliest time public and locally received | `max(public availability, received)` |

Date-only values do not become midnight UTC. Conservative end-of-date uses the next local midnight boundary with an explicit timezone. An uncertain receipt placeholder is marked partial. Capture time alone cannot prove public availability.

Bundles independently enforce source/public, receipt, and effective gates. `availability_age_ms`, `filing_age_ms`, and `reporting_period_age_days` remain separate. A newly received filing can describe an old period.

The presence, absence, form, or amendment status of a filing is objective metadata only. Phase 1E assigns no positive, negative, bullish, bearish, dilution, catalyst, squeeze, or trading meaning.

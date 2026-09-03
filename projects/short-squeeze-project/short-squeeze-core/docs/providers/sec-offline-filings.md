# Offline SEC-Shaped Filing Normalization

The SEC adapter accepts local sanitized JSON metadata only. It does not connect to SEC.gov or EDGAR, open URLs, download filings, parse HTML/XBRL, read credentials, or interpret filing content.

`SecFilingRecord` requires schema `SEC_FILING_V1`, type `SEC_FILING`, fixture origin, source record ID, and synthetic symbol. Documented aliases are `ticker`/`symbol`, `cik`/`issuer_cik`, `form`/`form_type`, `filed_date`/`filing_date`/`filed_at`, `acceptance_datetime`/`accepted_at`, `publication_datetime`/`published_at`, `filing_href`/`filing_url`, and `record_status`/`filing_status`. Unknown fields reject.

CIK accepts one to ten digits and normalizes to a ten-digit string. Accession accepts canonical dashed or unambiguous compact 18-digit form. Form is conservatively uppercased and supports explicit `/A`. The unchanged canonical payload contains form, accession, filed time, period of report, primary-document basename, and CIK. Auxiliary objective metadata remains provenance.

Primary documents must be sanitized basenames. Remote URLs, paths, query strings, and fragments are omitted and diagnosed. No reference is opened.

Explicit publication time is the first public-availability choice; otherwise exact SEC acceptance is used. Date-only publication requires strict rejection, conservative timezone-bound end-of-date, or an uncertain receipt-time placeholder. Receipt is adapter context ingestion. Effective time is the later of public availability and receipt. Period of report and filed date never grant availability.

Originals and amendments are immutable observations. A resolvable amended accession creates deterministic parent/correlation links. Missing links are partial evidence. Exact duplicates are suppressed; same-accession disagreements are preserved as conflicts; no winner is selected.

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider sec --input tests\fixtures\providers\sec\representative_cases.json --context tests\fixtures\providers\sec\context.json --case sec-complete-original-v1
```

Rejected normalization returns nonzero with structured diagnostics. Output contains no sentiment, catalyst, dilution, score, rank, recommendation, or trading interpretation.

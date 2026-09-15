# Public record primary-source verification

Lane I hardening: reconcile **replaceable aggregator rows** (LuxAlgo Market Trackers) against
**primary public authorities** without claiming live congressional feeds or SEC→opportunity
vertical readiness.

## Authorities

| Domain | Primary authority | Aggregator |
| --- | --- | --- |
| SEC Forms 3/4/5 | [SEC EDGAR](https://www.sec.gov/edgar) (`data.sec.gov` submissions JSON + archive documents) | `market_trackers.sec_insider` |
| Congressional PTR | [Senate eFD](https://efdsearch.senate.gov/) + [House Clerk disclosures](https://disclosures-clerk.house.gov/) | `market_trackers.congressional_disclosure` |

## Acceptance label

`PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY` — fixture/replay verification path is
implemented; evidence class remains `SOFTWARE/FIXTURE/REPLAY` unless a lawful live retrieval
is performed (then SEC document path may be `PROSPECTIVE_OBSERVATIONAL`).

**Not claimed:** `REALTIME_CONGRESSIONAL_FEED`, `SEC_TO_OPPORTUNITY_VERTICAL_READY`.

## SEC EDGAR path

- Uses existing `SecTransport` (declared User-Agent, throttle, cache, retries).
- Submissions JSON is matched by normalized accession (no Market Trackers dependency).
- Optional primary document bytes yield `source_hash_sha256` via `hash_document`.
- Output includes `edgar_primary` mapping compatible with `normalize_sec_insider_row(..., edgar_primary=...)`.

## Congressional PTR path

- Validates aggregator `provenance.sourceUrl` host against Senate eFD / House Clerk allowlists.
- **Automated document fetch:** `NOT_SUPPORTED` (no anti-bot or terms bypass).
- Optional `ptr_primary_metadata` fixture supplies chamber filing clocks for reconcile
  (`PRIMARY_SOURCE_PTR_WINS`).

## Artifact provenance fields

`PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_ARTIFACT` records:

- `primary_url`, `retrieval_time`, `source_hash_sha256`, `document_identifier`, `parser_version`
- Aggregator mapping (`upstream_row_id`, parser, retrievedAt)
- `realtime_congressional_feed_claim`: `NOT_CLAIMED`

## Code entrypoints

- `research.public_record_primary_source.verify_market_trackers_row`
- `market_trackers.sec_insider.primary_verification_bridge.build_adapter_prep_bundle_with_edgar_primary`
- `market_trackers.congressional_disclosure.primary_verification_bridge.build_adapter_prep_bundle_with_ptr_primary`
- `sec_edgar.primary_verification.fetch_and_verify_sec_insider_row` (opt-in live; requires `SEC_USER_AGENT`)

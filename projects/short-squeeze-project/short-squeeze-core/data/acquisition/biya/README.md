# BIYA historical acquisition evidence

This directory stores immutable raw acquisition responses, deterministic manifests, and
separate normalized derivatives for the Phase 2V outcome-data amendment.

- `raw/` contains exact provider/public response bytes. Existing files are never
  overwritten.
- `manifests/` contains one canonical manifest for every attempt, including failures.
- `normalized/` contains deterministic derivatives linked to a raw acquisition ID and
  hash.

Acquisition requires explicit symbol, provider, start, end, retrieval timestamp, time
zone, session scope, interval, adjustment policy, and output path. Manifests exclude
credentials, authentication parameters, account identifiers, private URLs, and absolute
local paths. Daily FINRA short-sale volume remains separate from published short
interest. Current borrow values are never substituted for unavailable history.

Raw evidence may be sanitized only when producing a separate public fixture or export;
the source bytes in this directory are not rewritten.


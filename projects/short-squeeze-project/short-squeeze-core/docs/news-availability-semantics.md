# News Availability Semantics

News eligibility requires all three point-in-time boundaries: provider availability (`source_timestamp`), local capture/receipt (`received_timestamp`), and `effective_timestamp = max(source, received)`. A publication date does not prove the local system had the record, and capture does not rewrite publication.

The independent `NEWS` coverage domain includes only observations with an explicit association to the requested symbol. Coverage does not merge news with market, borrow, published short-interest, SEC-filing, or trading-halt evidence. It reports missing or partial status and deterministic diagnostic codes when required evidence is absent or excluded.

Each selected observation may expose separate nonnegative publication, update, availability, capture, receipt, and effective ages when the underlying timestamp exists. Original publication remains distinct from provider updates and lifecycle availability.

News conflicts are limited to objective same-identity disagreements: headline, publication time, associated symbols, or canonical URL. Equal canonical URLs across providers create deterministic syndication relationships; observations and provider provenance remain separate.


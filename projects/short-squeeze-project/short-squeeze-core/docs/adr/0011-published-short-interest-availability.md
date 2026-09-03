# ADR 0011: Published Short-Interest Availability

## Context

Published short interest describes a settlement-period position but is normally published later. Treating settlement date or file capture as availability would introduce hindsight into historical evidence.

## Decision

For the supported offline FINRA-shaped record, `source_timestamp` is the defensible publication-availability boundary, `received_timestamp` is explicit ingestion time, and `effective_timestamp` is their maximum. Date-only publication requires strict rejection, a timezone-bound conservative end-of-day policy, or an explicitly uncertain receipt-time placeholder.

## Consequences

Point-in-time consumers can gate publication, receipt, and effective time separately. A recent receipt does not make the reported market period current, and capture time alone cannot prove publication.

## Rejected alternatives

Midnight UTC invents precision. Settlement time backdating creates look-ahead. Receipt-only gating can admit a record before its claimed publication.

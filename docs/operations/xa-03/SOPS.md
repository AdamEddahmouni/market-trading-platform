# XA-03 standard operating procedures

## SOP-XA03-001 — Second admitted source inspection

Inspect admitted CFTC positioning observations and cross-asset reference relationships through the source-neutral admission envelope.

### Steps

1. Run `xa03 status --json` to confirm unified admission registry state across FRED and CFTC verticals.
2. Run `xa03 validate --json` to verify catalog relationships and admitted market reports.
3. Run `xa03 admit-fixture --fixture positioning_reference_vertical.json --json` for fixture-backed acceptance admission.
4. Use `xa03 show-source <market_report_id> --json` to inspect observations and provenance.
5. Use `xa03 list-relationships --json` to inspect market report → XA futures family reference map.

### Authority

XA-03 inspection and fixture admission are reference-metadata operations. They grant no trading, ledger, analytical positioning, or motive-inference authority.

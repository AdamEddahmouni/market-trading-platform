"""Fixed-income source adapters and deterministic analytics (Screener S9).

Adapters normalize official publications into typed, provider-neutral
records; the Screener projection in ``ui_api.screener_bonds`` never reads
HTTP response syntax. Every source keeps its own clock:

- ``treasury_catalog``: Treasury Fiscal Data auctions + Monthly Statement of
  the Public Debt (security reference data; event clock).
- ``treasury_rates``: Treasury daily par nominal/real curves and bill rates
  (daily publication clock).
- ``fred_context``: FRED policy, credit, and conditions series through the
  existing ``fred`` client (series publication clock, point-in-time fields).
- ``finra_fixed_income``: FINRA TRACE capability and credential-gated
  aggregate statistics (never per-security prices without a licensed feed).
- ``analytics``: bond math with explicit conventions and failure codes.

Bonds are reference-only in IMP: nothing here creates an execution path.
"""

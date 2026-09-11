# FTEP Futures Asset-Class Profile V1

**Classification:** `PREIMPLEMENTATION_PROFILE`  
**Inherits:** `FTEP_CORE_V1`  
**Scope:** futures campaigns, including the candidate first ES campaign

## Mandatory futures semantics

A futures campaign must bind the **dated executable contract**, not only a continuous/family symbol. Preserve the continuous/family identity only as research/context when used.

The campaign manifest must record:

- exchange and product/family;
- exact contract month / canonical instrument key;
- tick size and tick value;
- contract multiplier and currency;
- exchange/session calendar and timezone;
- expiration/last-trade/settlement dates relevant to the campaign;
- roll policy and whether the campaign can cross a roll window;
- settlement treatment;
- initial/maintenance or Paper margin assumptions used by risk/execution;
- price-limit/circuit-breaker handling where applicable;
- transaction fees/commissions used in analysis;
- market-data capability contract(s), including L1/depth granularity actually available;
- contract-month liquidity/capacity limits;
- order types and execution-policy assumptions;
- external comparator scope/limitations when used.

## Continuous futures rule

Continuous futures series may be used for historical feature research only when the roll/back-adjustment methodology is explicit. They are non-executable. A forward/Paper order must resolve to a dated contract admitted by canonical instrument identity.

## Session and liquidity rule

Globex/extended-hours and regular/high-liquidity windows cannot be treated as equivalent without preregistration. The campaign must freeze its eligible session window and document any known liquidity differences relevant to fills/slippage.

## Roll and expiry rule

If a campaign approaches a roll/expiry window, the manifest must specify whether decisions are:

- prohibited in the window;
- bound to a fixed contract through the campaign;
- migrated under a preregistered deterministic roll rule; or
- split into separate campaign segments.

No post-hoc contract substitution is allowed.

## Margin and P&L

Risk and P&L calculations must use canonical futures multiplier/tick economics. Missing required margin facts fail closed for any claim that depends on sizing or account feasibility.

## Execution calibration

For execution-bearing campaigns, the calibration contract must be futures-specific and bind exact order types, contract month, data granularity and session window. If market evidence cannot observe queue/market-impact behavior, those claims remain explicitly out of scope even if a broker Paper comparator produces fills.

## First ES campaign open bindings

The following remain activation-manifest decisions rather than defaults:

- exact ES contract month;
- eligible Globex/session window;
- qualifying data provider(s) and market-data mode;
- whether depth beyond L1 is required by the hypothesis;
- signal-only vs execution-bearing first segment;
- external futures Paper/sandbox comparator;
- quantity/sizing rule;
- order policy;
- calibration thresholds;
- campaign duration and cohort sufficiency.

Until these are frozen, the profile supports planning but does not activate an ES campaign.

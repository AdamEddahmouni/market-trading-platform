# 14c — G6 Current-State Matrix (IBKR Observational L1/L2 Provider Adapter)

**Status:** G6 **closed** (2026-09-08, working tree uncommitted). Companion to
14a (G4) and 14b (G5). Baseline entering G6: G5 closed (BL-0212), FULL
4016/48/0 · FAST 21/0 · CHANGED 3481/48/0 · trading_correctness 122.
G6 closure: FULL **4107/48/0** · CHANGED **3572/48/0** · FAST 21/0 ·
ibkr_observational focused 91/0 · providers 216/0 · market_data 49/0 ·
order_book 87/0 · trading_correctness 122/0. Live provider:
**LIVE_PROVIDER_UNVERIFIED** (offline correctness only).

| Concern | Existing behavior (G5 close) | G6 target |
|---|---|---|
| IB connection | `tools/ibkr/tws_client.py` ib_insync `IB()` connect(host, port, clientId, readonly=True) — observational only; Client Portal REST client (`tools/ibkr/client.py`) loopback allowlist | Canonical `IbkrConnectionState` (DISCONNECTED/CONNECTING/CONNECTED/DEGRADED/FAILED) in `providers/ibkr_observational`; transport protocol injected (fakes in tests); offline gate blocks transport I/O |
| Contract mapping | `tools/ibkr/tws_client.py` `reqMatchingSymbols` → conId registry; `_contract(conid)`; `reqSecDefOptParams`; no canonical XA-01 binding | Canonical identity boundary: IB conId/qualified contract → XA-01 `instrument_id`; ambiguous/family/continuous → fail closed; provider metadata as provenance only |
| L1 bid/ask | `tws_client.py` snapshot via `ticker.bid/ask/last/bidSize` (reqMktData snapshot=True) — pull snapshot, not stream | Canonical L1 accumulation adapter: tickPrice/tickSize fields BID/BID_SIZE/ASK/ASK_SIZE/LAST/LAST_SIZE (+ delayed variants) accumulated per subscription; quote emitted only from real facts; never fabricate size=0 |
| L1 sizes | `bidSize` only in snapshot row | `BID_SIZE`/`ASK_SIZE`/`LAST_SIZE` tick accumulation |
| Last trade | `last` in snapshot row | `LAST`/`LAST_SIZE` accumulation; last price without last size stays truthful |
| L2 subscription | **none** — no `reqMktDepth`, `updateMktDepth`, `updateMktDepthL2` anywhere in tree (grep CONFIRMED at WS05 + G6) | `subscribe_l2` → transport `req_mkt_depth`; canonical adapter owns reqId↔subscription mapping |
| Depth operation mapping | documented only in 14b: operation 0=INSERT / 1=UPDATE / 2=DELETE (verified vs IBKR official docs `interactivebrokers.github.io/tws-api/market_depth.html`) | `DepthOperation.INSERT/UPDATE/DELETE`; RESET synthesized on subscribe/reconnect; verified constants + evidence in `constants.py` |
| Position/rank handling | canonical engine treats `position` as advisory rank metadata; price-keyed identity | Adapter-local per-subscription rank state resolves position → canonical price level; INSERT shifts ranks; UPDATE price-change translates DELETE+INSERT; DELETE resolves price from rank state (never blind provider delete price); disagreement → fail closed + RESET + diagnostic |
| Market-maker metadata | none | `updateMktDepthL2` `marketMaker` → `provenance["market_maker"]`; `isSmartDepth` → `provenance["is_smart_depth"]`; callback type → `provenance["callback_type"]`; never part of level identity |
| Entitlement state | `ProviderLifecycle.entitlement_state` ("UNKNOWN"); Moomoo `VerifiedCapabilityRegistry` probe-driven; IBKR has none | Canonical `EntitlementState` (UNKNOWN/ENTITLED/DELAYED/NOT_ENTITLED/ERROR); never map UNKNOWN→ENTITLED, DELAYED→real-time; error 354/10197 → NOT_ENTITLED/DELAYED |
| Pacing | `tools/ibkr/pacing.py` RequestPacer (token bucket, historical limiter, 429 penalty box) — REST path | Local configurable subscription cap (L1/L2 counts + configured max); IBKR documented depth cap 3–60 requests (error 309); pacing errors normalized (100/101/309); no fake provider-wide claims |
| Reconnect | `ProviderLifecycle` RECONNECTING state; Moomoo feed generation; no IBKR depth path | New generation/subscription identity on reconnect; canonical RESET; rank state cleared; resubscribe only authorized subscriptions; late old-generation callbacks rejected (GENERATION_MISMATCH) |
| Cancel subscription | none for streaming | `cancel_l1`/`cancel_l2` idempotent; unknown reqId cancellation → explicit diagnostic; no duplicate provider cancels |
| Generation | canonical engine `subscription_id` gate (G5) | Adapter issues canonical RESET with new `subscription_id` on subscribe/reconnect; engine generation advances; late events rejected by engine |
| Sequence semantics | canonical engine NO_SEQUENCE truthful default | IBKR provides no monotone provider sequence → `DepthUpdate.sequence=None` always; engine reports `NO_SEQUENCE`; reqId/callback-count/local-ordinal never fabricated as sequence |
| Capture/replay | `tools/ibkr/capture.py` JSONL request/response capture (REST); no callback capture | Provider-adapter callback capture format (callback kind, reqId, instrument_id, position, operation, side, price, size, market maker, received ns, error metadata, generation); replay through adapter normalization path → same canonical final state/hash |
| Offline guard | `tools/ibkr` `LiveGateDisabled` before any I/O; validate.py strips `IMP_LIVE_*` gates; MP_OFFLINE authoritative | Adapter config `live_enabled` fail-closed; offline mode → no connect/reqMktData/reqMktDepth/background reconnect; unit tests use fakes only; no CI contact with IBKR |
| Diagnostics | `ProviderLifecycle.to_dict()` + `health_payload()` (Moomoo) | Per-subscription diagnostics (state/entitlement/delayed/reqId/generation/last source+received time/last error), connection state, L1/L2 counts, book state/freshness/sequence (NO_SEQUENCE), reset/reconnect count, pacing/cap status; readiness READY/DEGRADED/UNAVAILABLE/FAILED per capability |

Verified IBKR facts (evidence for `constants.py` and mapping tests):
- `reqMktDepth`/`cancelMktDepth` names in Python/Java/C++ API (official docs).
- `updateMktDepth(reqId, position, operation, side, price, size)` and
  `updateMktDepthL2(reqId, position, marketMaker, operation, side, price, size, isSmartDepth)`
  — `isSmartDepth` True ⇒ marketMaker is the source exchange (API v974+).
- Operation constants: **0 = insert, 1 = update, 2 = delete/remove** (official docs).
- Side constants: **0 = ASK, 1 = BID** (ib_insync/IBApi `MarketDepthSide` convention; corroborated by G5 matrix 14b "BID/ASK reversed at the boundary").
- Depth request cap: min 3, max 60 active depth requests depending on market-data lines; error **309** = max 3 depth requests (TWS cap); error **316** = depth HALTED re-subscribe; error **317** = depth RESET — empty book before applying new entries.
- Pacing: error **100** = 50 msgs/sec exceeded; error **101** = max tickers reached (subscription cap).
- Entitlement: error **354** = "Not subscribed to requested market data" (delayed data may still be delivered); error **200** = no security definition found (contract); error **102** = duplicate ticker ID; error **300** = cancel of unknown ticker ID; error **310** = cancel of unknown depth.
- Connectivity: **1100** lost / **1101** restored-data-lost (resubscribe) / **1102** restored-data-maintained; **2103** farm disconnected; **2104/2106/2158** farm OK (informational); **502/504/326/1300** connection-level.

G6 does NOT add: Live execution, order placement/cancellation, account/portfolio trading
operations, unrestricted IB object exposure, browser automation, provider-framework
redesign, G5 engine redesign. Execution capability is never registered.
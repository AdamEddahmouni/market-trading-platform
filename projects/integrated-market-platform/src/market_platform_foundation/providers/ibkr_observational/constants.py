"""Verified IBKR TWS / IB Gateway callback constants (G6).

Single source of truth for every provider integer constant consumed by the
canonical IBKR observational adapter. Values are verified against:

- IBKR official TWS API "Market Depth (Level II)" documentation
  (https://interactivebrokers.github.io/tws-api/market_depth.html):
  operations are *insert (0), update (1), remove (2)*; callbacks are
  ``updateMktDepth(reqId, position, operation, side, price, size)`` and
  ``updateMktDepthL2(reqId, position, marketMaker, operation, side, price,
  size, isSmartDepth)``; requests are ``reqMktDepth`` / ``cancelMktDepth``.
- The G5 program matrix (``docs/audits/imp-reconciliation/14b``), which
  documented the G6 plan mapping ``operation 0=INSERT, 1=UPDATE, 2=DELETE``
  and ``side 0=ASK, 1=BID`` with BID/ASK reversed at the adapter boundary.
- ib_insync / IBApi convention (``MarketDepthOperation``: INSERT=0,
  UPDATE=1, DELETE=2; ``MarketDepthSide``: ASK=0, BID=1).
- IBApi ``TickType`` standard numbering for ``reqMktData`` fields: base
  types ``BID_SIZE=0`` ... ``LAST_SIZE=5`` and the delayed family
  ``DELAYED_BID=66`` ... ``DELAYED_LOW=75``.

Do not "fix" these numbers from memory: every consumer in this package
references the named constants, and the mapping tests assert the verified
values, so a future correction is a one-place change.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# market depth (reqMktDepth / updateMktDepth / updateMktDepthL2)
# --------------------------------------------------------------------------- #

#: EWrapper.updateMktDepth ``operation`` — insert a new row.
IB_OP_INSERT = 0
#: EWrapper.updateMktDepth ``operation`` — update the row at ``position``.
IB_OP_UPDATE = 1
#: EWrapper.updateMktDepth ``operation`` — delete/remove the row at ``position``.
IB_OP_DELETE = 2

#: EWrapper.updateMktDepth ``side`` — ask side (0).
IB_SIDE_ASK = 0
#: EWrapper.updateMktDepth ``side`` — bid side (1).
IB_SIDE_BID = 1

#: Valid depth operation integers (verified 0/1/2).
IB_DEPTH_OPERATIONS = frozenset({IB_OP_INSERT, IB_OP_UPDATE, IB_OP_DELETE})
#: Valid depth side integers (verified 0/1).
IB_DEPTH_SIDES = frozenset({IB_SIDE_ASK, IB_SIDE_BID})

# --------------------------------------------------------------------------- #
# reqMktData tick fields (EWrapper.tickPrice / tickSize ``field`` argument)
# --------------------------------------------------------------------------- #

TICK_BID_SIZE = 0
TICK_BID = 1
TICK_ASK = 2
TICK_ASK_SIZE = 3
TICK_LAST = 4
TICK_LAST_SIZE = 5
TICK_HIGH = 6
TICK_LOW = 7
TICK_VOLUME = 8
TICK_CLOSE = 9

# Delayed family (IBApi TickType standard numbering).
TICK_DELAYED_BID = 66
TICK_DELAYED_ASK = 67
TICK_DELAYED_LAST = 68
TICK_DELAYED_BID_SIZE = 69
TICK_DELAYED_ASK_SIZE = 70
TICK_DELAYED_LAST_SIZE = 71
TICK_DELAYED_VOLUME = 72
TICK_DELAYED_CLOSE = 73
TICK_DELAYED_HIGH = 74
TICK_DELAYED_LOW = 75

#: tick fields carrying a price (tickPrice).
TICK_PRICE_FIELDS = frozenset(
    {
        TICK_BID,
        TICK_ASK,
        TICK_LAST,
        TICK_HIGH,
        TICK_LOW,
        TICK_CLOSE,
        TICK_DELAYED_BID,
        TICK_DELAYED_ASK,
        TICK_DELAYED_LAST,
        TICK_DELAYED_CLOSE,
        TICK_DELAYED_HIGH,
        TICK_DELAYED_LOW,
    }
)
#: tick fields carrying a size (tickSize).
TICK_SIZE_FIELDS = frozenset(
    {
        TICK_BID_SIZE,
        TICK_ASK_SIZE,
        TICK_LAST_SIZE,
        TICK_VOLUME,
        TICK_DELAYED_BID_SIZE,
        TICK_DELAYED_ASK_SIZE,
        TICK_DELAYED_LAST_SIZE,
        TICK_DELAYED_VOLUME,
    }
)
#: any delayed tick field (delayed ⇒ never classified real-time).
TICK_DELAYED_FIELDS = frozenset(
    {
        TICK_DELAYED_BID,
        TICK_DELAYED_ASK,
        TICK_DELAYED_LAST,
        TICK_DELAYED_BID_SIZE,
        TICK_DELAYED_ASK_SIZE,
        TICK_DELAYED_LAST_SIZE,
        TICK_DELAYED_VOLUME,
        TICK_DELAYED_CLOSE,
        TICK_DELAYED_HIGH,
        TICK_DELAYED_LOW,
    }
)

# --------------------------------------------------------------------------- #
# error code families (verified against the official message-codes reference)
# --------------------------------------------------------------------------- #

#: 100 — max 50 messages/second exceeded (pacing violation, TWS may disconnect).
ERROR_CODE_100_MAX_MSG_RATE = 100
#: 101 — max number of market data tickers reached (account cap).
ERROR_CODE_101_MAX_TICKERS = 101
#: 102 — duplicate ticker ID (an active market data request uses this reqId).
ERROR_CODE_102_DUPLICATE_TICKER = 102
#: 200 — no security definition found for the request (contract resolution).
ERROR_CODE_200_NO_SECURITY_DEFINITION = 200
#: 300 — cancel of a ticker ID with no current subscription.
ERROR_CODE_300_CANCEL_UNKNOWN_TICKER = 300
#: 309 — max (3) market depth requests reached (depth subscription cap).
ERROR_CODE_309_MAX_DEPTH_REQUESTS = 309
#: 310 — cancel of a market depth ticker that is not active.
ERROR_CODE_310_CANCEL_UNKNOWN_DEPTH = 310
#: 316 — market depth data has been HALTED; re-subscribe required.
ERROR_CODE_316_DEPTH_HALTED = 316
#: 317 — market depth data has been RESET; empty the book before new entries.
ERROR_CODE_317_DEPTH_RESET = 317
#: 326 — unable to connect, client id already in use.
ERROR_CODE_326_CLIENT_ID_IN_USE = 326
#: 354 — not subscribed to requested market data (entitlement missing;
#: delayed data may still be delivered).
ERROR_CODE_354_NOT_SUBSCRIBED = 354
#: 502 — couldn't connect to TWS (API not enabled / wrong port).
ERROR_CODE_502_CONNECT_FAILED = 502
#: 504 — not connected; request issued without an active connection.
ERROR_CODE_504_NOT_CONNECTED = 504
#: 1100 — connectivity between IB and TWS lost.
ERROR_CODE_1100_CONNECTIVITY_LOST = 1100
#: 1101 — connectivity restored, market data requests LOST (resubscribe).
ERROR_CODE_1101_RESTORED_DATA_LOST = 1101
#: 1102 — connectivity restored, data maintained (no resubscribe needed).
ERROR_CODE_1102_RESTORED_DATA_MAINTAINED = 1102
#: 1300 — TWS socket port reset; connection dropped.
ERROR_CODE_1300_SOCKET_PORT_RESET = 1300
#: 2103 — a market data farm is disconnected.
ERROR_CODE_2103_MD_FARM_DISCONNECTED = 2103
#: 2104 — market data farm connection is OK (informational).
ERROR_CODE_2104_MD_FARM_OK = 2104
#: 2158 — sec-def data farm connection is OK (informational).
ERROR_CODE_2158_SECDEF_FARM_OK = 2158

#: Entitlement failure codes (documented "not subscribed / no permission").
ENTITLEMENT_ERROR_CODES = frozenset({ERROR_CODE_354_NOT_SUBSCRIBED})
#: Pacing / subscription-cap codes.
PACING_ERROR_CODES = frozenset(
    {
        ERROR_CODE_100_MAX_MSG_RATE,
        ERROR_CODE_101_MAX_TICKERS,
        ERROR_CODE_309_MAX_DEPTH_REQUESTS,
    }
)
#: Contract-resolution codes.
CONTRACT_ERROR_CODES = frozenset({ERROR_CODE_200_NO_SECURITY_DEFINITION})
#: Subscription-level codes (unknown/cancel/halt/reset).
SUBSCRIPTION_ERROR_CODES = frozenset(
    {
        ERROR_CODE_102_DUPLICATE_TICKER,
        ERROR_CODE_300_CANCEL_UNKNOWN_TICKER,
        ERROR_CODE_310_CANCEL_UNKNOWN_DEPTH,
        ERROR_CODE_316_DEPTH_HALTED,
        ERROR_CODE_317_DEPTH_RESET,
    }
)
#: Connection-level codes.
CONNECTION_ERROR_CODES = frozenset(
    {
        ERROR_CODE_326_CLIENT_ID_IN_USE,
        ERROR_CODE_502_CONNECT_FAILED,
        ERROR_CODE_504_NOT_CONNECTED,
        ERROR_CODE_1100_CONNECTIVITY_LOST,
        ERROR_CODE_1101_RESTORED_DATA_LOST,
        ERROR_CODE_1102_RESTORED_DATA_MAINTAINED,
        ERROR_CODE_1300_SOCKET_PORT_RESET,
        ERROR_CODE_2103_MD_FARM_DISCONNECTED,
    }
)
#: Informational / healthy notifications (not errors).
INFORMATIONAL_ERROR_CODES = frozenset(
    {ERROR_CODE_2104_MD_FARM_OK, ERROR_CODE_2158_SECDEF_FARM_OK}
)

#: Documented market-data request rate ceiling (messages/second).
IB_MAX_MSG_RATE_PER_SECOND = 50
#: Minimum configured local depth-subscription cap (IBKR documents 3 as the
#: TWS-side minimum; local policy may be stricter).
IB_DEPTH_SUBSCRIPTION_FLOOR = 3
#: IBKR documented maximum active depth requests (top of the line-dependent
#: range; entitlement-dependent, so the local cap is configurable).
IB_DEPTH_SUBSCRIPTION_CEILING = 60

# --------------------------------------------------------------------------- #
# reqTickByTickData (EWrapper.tickByTickAllLast / tickByTickBidAsk / …)
# Verified against IB TWS API tick-by-tick documentation and ib_insync
# ``TickByTickAllLast`` wrapper signature:
# ``tickByTickAllLast(reqId, tickType, time, price, size, tickAttribLast,
# exchange, specialConditions)``.
# --------------------------------------------------------------------------- #

#: ``reqTickByTickData`` tickType string for all last prints.
TICK_BY_TICK_ALL_LAST = "AllLast"
#: ``tickByTickAllLast`` callback ``tickType`` — last print only.
TICK_BY_TICK_TYPE_LAST = 1
#: ``tickByTickAllLast`` callback ``tickType`` — all last prints.
TICK_BY_TICK_TYPE_ALL_LAST = 2

__all__ = [
    "CONNECTION_ERROR_CODES",
    "CONTRACT_ERROR_CODES",
    "ENTITLEMENT_ERROR_CODES",
    "ERROR_CODE_100_MAX_MSG_RATE",
    "ERROR_CODE_101_MAX_TICKERS",
    "ERROR_CODE_102_DUPLICATE_TICKER",
    "ERROR_CODE_1100_CONNECTIVITY_LOST",
    "ERROR_CODE_1101_RESTORED_DATA_LOST",
    "ERROR_CODE_1102_RESTORED_DATA_MAINTAINED",
    "ERROR_CODE_1300_SOCKET_PORT_RESET",
    "ERROR_CODE_200_NO_SECURITY_DEFINITION",
    "ERROR_CODE_2103_MD_FARM_DISCONNECTED",
    "ERROR_CODE_2104_MD_FARM_OK",
    "ERROR_CODE_2158_SECDEF_FARM_OK",
    "ERROR_CODE_300_CANCEL_UNKNOWN_TICKER",
    "ERROR_CODE_309_MAX_DEPTH_REQUESTS",
    "ERROR_CODE_310_CANCEL_UNKNOWN_DEPTH",
    "ERROR_CODE_316_DEPTH_HALTED",
    "ERROR_CODE_317_DEPTH_RESET",
    "ERROR_CODE_326_CLIENT_ID_IN_USE",
    "ERROR_CODE_354_NOT_SUBSCRIBED",
    "ERROR_CODE_502_CONNECT_FAILED",
    "ERROR_CODE_504_NOT_CONNECTED",
    "IB_DEPTH_SUBSCRIPTION_CEILING",
    "IB_DEPTH_SUBSCRIPTION_FLOOR",
    "IB_MAX_MSG_RATE_PER_SECOND",
    "IB_DEPTH_OPERATIONS",
    "IB_DEPTH_SIDES",
    "IB_OP_DELETE",
    "IB_OP_INSERT",
    "IB_OP_UPDATE",
    "IB_SIDE_ASK",
    "IB_SIDE_BID",
    "INFORMATIONAL_ERROR_CODES",
    "PACING_ERROR_CODES",
    "SUBSCRIPTION_ERROR_CODES",
    "TICK_ASK",
    "TICK_ASK_SIZE",
    "TICK_BID",
    "TICK_BID_SIZE",
    "TICK_BY_TICK_ALL_LAST",
    "TICK_BY_TICK_TYPE_ALL_LAST",
    "TICK_BY_TICK_TYPE_LAST",
    "TICK_CLOSE",
    "TICK_DELAYED_ASK",
    "TICK_DELAYED_ASK_SIZE",
    "TICK_DELAYED_BID",
    "TICK_DELAYED_BID_SIZE",
    "TICK_DELAYED_CLOSE",
    "TICK_DELAYED_FIELDS",
    "TICK_DELAYED_HIGH",
    "TICK_DELAYED_LAST",
    "TICK_DELAYED_LAST_SIZE",
    "TICK_DELAYED_LOW",
    "TICK_DELAYED_VOLUME",
    "TICK_HIGH",
    "TICK_LAST",
    "TICK_LAST_SIZE",
    "TICK_LOW",
    "TICK_PRICE_FIELDS",
    "TICK_SIZE_FIELDS",
    "TICK_VOLUME",
]
"""Public Crypto venue market data (Screener S10).

- ``ws_client``: a standard-library RFC 6455 client (the dependency lock
  prohibits third-party WebSocket packages), allowlisted to venue hosts.
- ``kraken_book``: Kraken Spot WebSocket v2 ``book`` snapshot + deltas on the
  canonical ``IncrementalOrderBook``, with the venue CRC32 checksum.
- ``kraken_stream``: the single subscription authority for the selected-pair
  ``trade`` and ``book`` channels behind the S4 Order Flow, CVD, and Level 2
  panels.

The universe catalog, all-pair ticker snapshot, and OHLC bars are REST and
live in ``ui_api.screener_crypto``. Everything here is public, anonymous,
observational market data; nothing authenticates, places, or routes orders.
"""

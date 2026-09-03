# Trade and Quote Sequence and Lifecycle Timeline

The deterministic `TESTA` timeline contains `ORIGINAL` trade and quote records, later `CORRECTED` records, a later `CANCELLED` quote, and a later cancelled trade fixture:

1. Before original publication, neither record is available.
2. After publication but before receipt, neither record is locally available.
3. After original receipt, originals enter the bundle.
4. Before correction receipt, originals remain the latest eligible versions.
5. After correction receipt, originals and corrections coexist with immutable relationships.
6. Before cancellation receipt, the quote remains in its prior state.
7. After cancellation receipt, the cancellation is visible without removing earlier versions.

Sequence ordering remains separate from arrival and event ordering. Compatible streams diagnose duplicate, conflicting, reset, and out-of-order values. Missing and unknown scopes remain explicit; incompatible scopes are not compared.


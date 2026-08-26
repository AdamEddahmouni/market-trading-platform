# BUILD 35 Known Limitations

- single-machine local deployment qualification only
- no production cloud infrastructure or external release registry service
- release approval is local/single-user fixture qualification
- BUILD26 forward qualification disposition INSUFFICIENT_FORWARD_EVIDENCE
- BUILD29 canary disposition CANARY_NOT_EXECUTED — fixture qualification only
- limited real live canary sample — zero real broker submits in qualification
- provider redundancy not exercised against live providers
- single-host deployment — no HA or multi-instance
- no automatic broker failover by design
- no derivatives live certification
- human session authorization and per-order confirmation remain mandatory
- release approval does not authorize autonomous live trading
- some acceptance domains rely on deterministic fixtures rather than real live observations
- insufficient long-duration real pilot evidence

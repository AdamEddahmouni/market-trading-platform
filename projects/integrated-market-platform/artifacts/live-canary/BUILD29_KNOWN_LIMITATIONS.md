# BUILD 29 Known Limitations

- First canary uses absolute micro-notional caps, not NAV-scaled limits.
- Only US cash equities LONG-only in default first-canary policy.
- No margin, shorting, derivatives, or outside-RTH in default policy.
- Real broker submission requires explicit human authorization per session.
- Per-order human confirmation required for first canary.
- Successful canary does not enable autonomous live trading.
- Global live kill switch remains ACTIVE_BLOCK; canary is narrowly scoped permit.
- No certified live broker available by default — real canary may not execute.
- REAL_CANARY_NOT_EXECUTED
- NO_EXPLICIT_HUMAN_AUTHORIZATION

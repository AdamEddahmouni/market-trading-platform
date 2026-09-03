# BUILD 30 Known Limitations

- First canary uses absolute micro-notional caps, not NAV-scaled limits.
- Only US cash equities LONG-only in default first-canary policy.
- No margin, shorting, derivatives, or outside-RTH in default policy.
- Real broker submission requires explicit human authorization per session.
- Per-order human confirmation required for first canary.
- Successful canary does not enable autonomous live trading.
- Global live kill switch remains ACTIVE_BLOCK; canary is narrowly scoped permit.
- No certified live broker available by default — real canary may not execute.
- BUILD30 supervises repeated canary sessions — not autonomous live trading.
- Program policy is an operational envelope; each session still requires fresh authorization.
- Per-order human confirmation remains mandatory across all sessions.
- Program caps accumulate across sessions and cannot increase from success.
- Critical incidents require manual resume approval before new sessions.
- Stale order confirmations are invalidated on restart.
- Cooldown expiry does not auto-start the next session.

- REAL_REPEATED_CANARY_NOT_EXECUTED
- NO_EXPLICIT_HUMAN_SESSION_AUTHORIZATION_FOR_REAL_ORDERS

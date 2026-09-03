# BUILD 33 Known Limitations

- bounded supervised production pilot — not unrestricted production rollout
- no autonomous live trading authority added by BUILD 33
- human session authorization and per-order confirmation remain mandatory
- market-data provider failover is deterministic; live broker failover is NOT automatic
- fallback provider must independently satisfy freshness and health requirements
- pilot caps are additional ceilings and cannot increase from operational success
- runbook exercises use fixtures and isolated stores only
- long-duration evidence limited to deterministic virtual endurance in CI
- single-host local qualification only
- external alert delivery not configured by default (local/console adapter only)
- no alternate live broker certified for automatic failover
- provider redundancy may be fixture-tested when only one live provider available
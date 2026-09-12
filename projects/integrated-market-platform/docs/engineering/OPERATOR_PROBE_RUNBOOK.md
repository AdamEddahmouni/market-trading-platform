# Operator probe runbook (FTEP-V1 activation)

**Classification:** `OPERATOR_SOP` (secret-free)  
**Scope:** Refresh local provider evidence for Wave A / capability-matrix reconciliation.  
**Does not:** place orders, enable Live trading, freeze manifests, or mutate activation state.

Prerequisites: [PROVIDER_READINESS.md](./PROVIDER_READINESS.md), [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md).

## Safety defaults

- Keep `IMP_LIVE_OBSERVATIONAL`, `IMP_MOOMOO_LIVE`, and broker live gates **unset** unless a provider doc explicitly requires a read-only observational gate for probes.
- Never commit `.env`, private provider files, probe JSON containing account identifiers, or API key values.
- Write fresh probe reports under `.local/` or `evidence/` only when the operator accepts overwriting dated artifacts; prefer timestamped filenames under `.local/` for ad-hoc runs.
- After probes, regenerate the capability matrix snapshot (final step).

## 1. Moomoo OpenD + SDK 3.11

1. Install/start **Moomoo OpenD** on loopback `127.0.0.1:11111` and sign in with an entitled account (see [MOOMOO_OBSERVATIONAL.md](../providers/MOOMOO_OBSERVATIONAL.md)).
2. Use a **Python 3.11** venv with the external `moomoo-api` SDK (documented in provider doc; not vendored in IMP).
3. From IMP root with `PYTHONPATH=src`:

   ```powershell
   python tools/moomoo/probe.py
   ```

4. Confirm the report lists observational capabilities; for FTEP-V1-001 ES context, verify **US futures quote** entitlement rows are present (not stale `UNAVAILABLE` from Wave A).
5. Optional loopback-only readiness merge:

   ```powershell
   python tools/provider_readiness.py --probe-local --json
   ```

## 2. Finviz Elite / discovery

1. Configure Finviz credentials per [FINVIZ_ELITE.md](../providers/FINVIZ_ELITE.md) in the ignored private provider file (no values in git).
2. Run the bounded capability probe:

   ```powershell
   python tools/finviz/probe.py
   ```

3. If MFA/CAPTCHA blocks automation, record operator completion in your local run notes only (not in repo secrets).

## 3. IBKR observational canary

1. Start **Client Portal Gateway** or **TWS** per [IBKR_OBSERVATIONAL.md](../providers/IBKR_OBSERVATIONAL.md); complete manual login.
2. Run a single-symbol canary (read-only):

   ```powershell
   python tools/ibkr/probe.py --symbol AAPL --output $env:TEMP\ibkr-canary-report.json
   ```

3. Confirm transport identity and redaction in the report; do not check reports into git if they contain account identifiers.

## 4. Alpaca / Tradier (G-A5 broker candidates)

1. Configure ignored credentials per provider docs; keep execution gates off.
2. Run existing broker audit probes referenced in [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md) and Wave A broker audit artifact `artifacts/wave-a-findings/ibkr-tradier-alpaca-audit.json`.
3. Use `python tools/provider_readiness.py audit --json` to merge matrix + gate rows after local configuration changes.

## 5. News bounded probe (optional, key-gated)

```powershell
python tools/news/probe.py --symbol AAPL
```

Requires `NEWSAPI_API_KEY` / `FINNHUB_API_KEY` in ignored config. Does not satisfy historical PIT news archive claims (see `EXT-NEWSAPI-FINNHUB-PIT` in [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](./FTEP_V1_ACTIVATION_BLOCKER_REPORT.md)).

## 6. Regenerate capability-matrix snapshot

After any probe refresh:

```powershell
python tools/providers/capability_matrix.py --output artifacts/wave-a-findings/capability-matrix-snapshot.json
python tools/imp.py providers campaign-readiness FTEP-V1-001 --json
```

Expect **NOT_READY** until owner decisions (`OWNER-OD-1-11`), calibration thresholds, and entitlement gaps clear. A fail-closed readiness JSON is success for governance.

## 7. Research export manifest (offline, optional)

For DECISION-RESEARCH or fixture lanes, bind dataset + cutoff without network access:

```python
from market_platform_foundation.research.pit_export import build_research_export_from_events
```

See `tests/research/test_pit_export.py` and `src/market_platform_foundation/research/pit_export.py` (PIT-A-001).

## Related

- Blocker consolidation: [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](./FTEP_V1_ACTIVATION_BLOCKER_REPORT.md)
- Machine-readable audit: [artifacts/ftep-v1-activation-goal-audit.json](../../artifacts/ftep-v1-activation-goal-audit.json)

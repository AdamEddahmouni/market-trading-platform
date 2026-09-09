# Product acceptance E2E (G15 / BL-0802)

Browser-level product acceptance runs against a **deterministic fixture-only**
stack. It does not require a pre-running developer server, live broker
connectivity, or IBKR entitlements.

## Prerequisites

- Python 3.11 project venv (`.venv`)
- Node.js + npm
- Playwright browsers installed once:

```powershell
cd e2e
npm install
npx playwright install chromium
```

## Canonical commands

From the IMP repository root:

```powershell
# E2E closure gate (manifest tier: e2e)
python tools/imp.py validate e2e

# Focused browser suite only (harness + Playwright)
.\.venv\Scripts\python.exe -m unittest tests.product_acceptance.test_browser_acceptance -v
```

## Startup path

1. `tools/e2e/harness.py` starts UI API on `127.0.0.1:8766` with
   `IMP_PAPER_EXECUTION=1`, fixture replay, and isolated `IMP_STATE_DIR`.
2. Vite dev server starts on `127.0.0.1:5173` (proxy to API).
3. Harness opens Paper session and scrubs replay to a fillable cursor.
4. Playwright runs against `IMP_E2E_UI_BASE`.
5. Harness terminates API/UI and removes temp state on completion or failure.

## Artifacts on failure

- `.local/e2e/api.log` — backend log
- `.local/e2e/ui.log` — frontend log
- `.local/e2e/test-results/` — Playwright traces/screenshots
- `.local/e2e/playwright-report/` — HTML report (not committed)

## Validation pyramid placement

| Tier | Includes browser E2E? |
|------|------------------------|
| FAST | No |
| CHANGED | Only when `e2e/` or product acceptance sources change |
| E2E | Yes (`python tools/imp.py validate e2e`) |
| FULL | No (backend offline suites only) |

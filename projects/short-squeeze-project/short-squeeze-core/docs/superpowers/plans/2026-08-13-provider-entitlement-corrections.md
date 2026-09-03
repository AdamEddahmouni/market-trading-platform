# Provider Entitlement Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct unsupported provider-plan and entitlement claims while preserving the screener's read-only, evidence-gated behavior.

**Architecture:** Documentation records provider conditions independently from feature availability. Runtime messages report the observed provider response without drawing unsupported plan conclusions. The unimplemented IBKR borrow-fee adapter advertises no unverified request mechanism.

**Tech Stack:** Python 3.12, pytest, Markdown.

## Global Constraints

- Do not add providers, credentials, scraping, trading features, or external network calls to tests.
- Preserve `UNKNOWN`/unavailable evidence behavior.
- Cite first-party sources for every plan, entitlement, licensing, or rate-limit assertion.

---

### Task 1: Correct runtime provider messages

**Files:**
- Modify: `apps/research_screener/news_live.py:319-321`
- Modify: `apps/research_screener/finnhub_live.py:137-140`
- Modify: `apps/research_screener/borrow_fee_live.py:1-71`
- Test: `tests/app/test_news_orchestrator.py`
- Test: `tests/app/test_borrow_fee_live.py`

**Interfaces:**
- Produces: non-fatal `last_error` wording for Finnhub HTTP 403 responses and accurate `status()["detail"]` messages for the borrow-fee adapter.

- [x] **Step 1: Write failing tests**

```python
def test_finnhub_403_reports_account_access_not_plan(monkeypatch):
    provider = FinnhubNewsProvider("test-token")
    # mocked HTTP 403
    provider.fetch_news("AAA", force=True)
    assert "account access" in provider.status()["last_error"].lower()
    assert "premium" not in provider.status()["last_error"].lower()

def test_borrow_fee_status_does_not_claim_generic_tick_258():
    assert "258" not in BorrowFeeProvider().status()["detail"]
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/app/test_news_orchestrator.py tests/app/test_borrow_fee_live.py -q`

Expected: FAIL because current messages contain `premium` and `258`.

- [x] **Step 3: Make the minimal changes**

```python
self._last_error = "Finnhub company-news access was denied for this account or request."
```

Replace the borrow-fee generic-tick claim with a statement that the adapter is not implemented and requires a verified IBKR API mechanism and entitlement.

- [x] **Step 4: Run focused tests**

Run: `python -m pytest tests/app/test_news_orchestrator.py tests/app/test_borrow_fee_live.py -q`

Expected: PASS.

### Task 2: Correct provider and collector reference documentation

**Files:**
- Modify: `docs/PROVIDERS.md`
- Modify: `docs/COLLECTORS.md`

**Interfaces:**
- Produces: provider-by-provider capability matrix with current plan, entitlement, license, freshness, and source links.

- [x] **Step 1: Write the documentation assertions into the source matrix**

Add first-party URLs for Finviz, NewsAPI, Finnhub, SEC EDGAR, IBKR, FinBERT, FINRA, yfinance, Polygon, Alpha Vantage, and Reddit. Distinguish FinBERT's three model labels from the application's aggregate `MIXED` label.

- [x] **Step 2: Verify documentation claims**

Run: `rg -n "requires premium plan|generic tick 258" docs apps/research_screener`

Expected: no unsupported Finnhub premium claim or IBKR generic-tick claim; FinBERT usage is explicitly scoped.

### Task 3: Run the complete verification suite

**Files:**
- Test: `tests/`

- [x] **Step 1: Run all tests**

Run: `python -m pytest -p no:cacheprovider --basetemp .pytest-run`

Expected: PASS with zero failures.

Collection restored via `scripts/acquisition/acquire_biya_history.py`. Focused entitlement tests, outcome CLI tests, CI subset, and frozen integration acceptance pass. Compatibility isolation tests fail as expected after provider entitlement edits.

- [x] **Step 2: Run frozen integration acceptance**

Run: `python tools/integration_acceptance.py --mode frozen`

Expected: PASS with no live provider calls.

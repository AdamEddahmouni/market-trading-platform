"""StockTwits scanner that applies keyword catalyst detection.

Purpose
-------
Fetch recent StockTwits posts for a ticker and aggregate tiered keyword scores
into HIGH_ALERT / WATCH / IGNORE escalation levels.

Pipeline role
-------------
``scan_ticker_social_signal`` is called from ``main.scan_social_for_ticker``
(parallelized in ``refresh_watchlist_and_social``). Results tag watchlist rows
with ``social_signal_level`` and ``social_triggered_posts``.

Key outputs
-----------
``{escalation_level, total_score, triggered_posts, reason_code, posts_fetched}``.

Handoff notes
-------------
**Reusable (equity/futures):** Public StockTwits API pattern, post-age filter,
keyword scoring integration — works for any cashtag symbol (including some futures
ETFs/proxies).

**Options-only coupling:** Keywords mention "unusual options activity" but logic
is symbol-agnostic.

**Rate limits:** Uses per-thread cloudscraper; proxy env cleared on import path.
"""

from __future__ import annotations

import os
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import cloudscraper

try:
    from social.keyword_detector import get_escalation_level, score_post_for_catalyst
except ImportError:  # Allows running this file directly from inside its folder.
    from keyword_detector import get_escalation_level, score_post_for_catalyst

_PROXY_ENV_CLEARED = False
_THREAD_LOCAL = threading.local()


def get_thread_local_scraper() -> Any:
    """
    Return a per-thread cloudscraper session for connection reuse.

    Inputs:
    - None.

    Output:
    - cloudscraper session object.

    Why this exists:
    - Reusing sessions avoids repeated TLS/session setup overhead.
    """
    existing = getattr(_THREAD_LOCAL, "scraper", None)
    if existing is not None:
        return existing
    created = cloudscraper.create_scraper()
    try:
        created.trust_env = False
    except Exception:
        pass
    _THREAD_LOCAL.scraper = created
    return created


def disable_proxy_env_if_present() -> None:
    """
    Remove proxy environment variables for this Python process.

    Inputs:
    - None.

    Output:
    - None.

    Why this exists:
    - Some local shells export proxy vars that can block StockTwits API
      calls with proxy tunnel errors.
    """
    global _PROXY_ENV_CLEARED
    if _PROXY_ENV_CLEARED:
        return

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    _PROXY_ENV_CLEARED = True


def fetch_stocktwits_posts(
    ticker: str,
    posts_to_fetch: int = 30,
    request_timeout_seconds: int = 8,
    scraper: Optional[Any] = None,
    max_retries: int = 1,
    retry_backoff_ms: int = 250,
    quiet_expected_misses: bool = True,
) -> Dict[str, Any]:
    """
    Fetch recent StockTwits posts for a ticker using the public API.

    Inputs:
    - ticker: stock symbol like 'AAPL'.
    - posts_to_fetch: maximum number of posts to keep.
    - request_timeout_seconds: HTTP timeout per request.
    - scraper: optional pre-created cloudscraper session to reuse connections.

    Output:
    - Dictionary with:
      - posts: list of post dictionaries
      - reason_code: short status label for observability

    Why this exists:
    - We isolate API fetching so network failures can be handled cleanly
      without crashing the rest of the social-scanning pipeline.
    """
    symbol = ticker.upper().strip()
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"

    disable_proxy_env_if_present()
    active_scraper = scraper or get_thread_local_scraper()
    attempts = max(1, int(max_retries) + 1)

    for attempt in range(attempts):
        try:
            response = active_scraper.get(url, timeout=request_timeout_seconds)
            if response.status_code == 404:
                # Some symbols are not supported by the endpoint. Treat as no data.
                return {"posts": [], "reason_code": "symbol_not_found", "posts_fetched": 0}
            if response.status_code == 429:
                if attempt + 1 < attempts:
                    time.sleep(max(0.0, float(retry_backoff_ms)) / 1000.0 * (attempt + 1))
                    continue
                if not quiet_expected_misses:
                    print(f"[stocktwits_scanner] Rate limited (429) for {symbol}. Try again later.")
                return {"posts": [], "reason_code": "rate_limited", "posts_fetched": 0}
            if response.status_code != 200:
                if not quiet_expected_misses:
                    print(f"[stocktwits_scanner] API error {response.status_code} for {symbol}.")
                return {"posts": [], "reason_code": f"http_{response.status_code}", "posts_fetched": 0}

            payload = response.json()
            messages = payload.get("messages", [])
            selected = messages[:posts_to_fetch]
            return {"posts": selected, "reason_code": "ok", "posts_fetched": len(selected)}
        except Exception as error:  # Defensive fallback for network/JSON failures.
            if attempt + 1 < attempts:
                time.sleep(max(0.0, float(retry_backoff_ms)) / 1000.0 * (attempt + 1))
                continue
            if not quiet_expected_misses:
                print(f"[stocktwits_scanner] Failed to fetch posts for {symbol}: {error}")
            return {"posts": [], "reason_code": "fetch_error", "posts_fetched": 0}
    return {"posts": [], "reason_code": "fetch_error", "posts_fetched": 0}


def scan_ticker_social_signal(
    ticker: str,
    posts_to_fetch: int = 30,
    request_timeout_seconds: int = 8,
    max_post_age_hours: int = 24,
    high_alert_threshold: int = 3,
    watch_threshold: int = 1,
    max_retries: int = 1,
    retry_backoff_ms: int = 250,
    quiet_expected_misses: bool = True,
    enable_keyword_aliases: bool = True,
    scraper: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Scan StockTwits posts and aggregate catalyst keyword scores.

    Inputs:
    - ticker: stock symbol like 'AAPL'.
    - posts_to_fetch: number of recent posts to examine.
    - request_timeout_seconds: HTTP timeout per request.
    - max_post_age_hours: ignore posts older than this many hours.
    - scraper: optional pre-created cloudscraper session.

    Output:
    - Dictionary with:
      - escalation_level
      - total_score
      - triggered_posts (list of matching post details)

    Why this exists:
    - This converts many raw social posts into one structured signal
      that the decision engine can combine with news sentiment.
    """
    fetch_result = fetch_stocktwits_posts(
        ticker=ticker,
        posts_to_fetch=posts_to_fetch,
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
        retry_backoff_ms=retry_backoff_ms,
        quiet_expected_misses=quiet_expected_misses,
        scraper=scraper,
    )
    posts = fetch_result.get("posts", [])
    upstream_reason = str(fetch_result.get("reason_code", "unknown"))
    posts_fetched = int(fetch_result.get("posts_fetched", len(posts)))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_post_age_hours)
    total_score = 0
    triggered_posts: List[Dict[str, Any]] = []
    recent_posts_scanned = 0

    for post in posts:
        created_at_text = str(post.get("created_at", ""))
        try:
            created_at_dt = datetime.fromisoformat(created_at_text.replace("Z", "+00:00"))
            if created_at_dt.tzinfo is None:
                created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
            else:
                created_at_dt = created_at_dt.astimezone(timezone.utc)
            if created_at_dt < cutoff:
                continue
        except Exception:
            # If created_at cannot be parsed, keep defensive behavior and skip.
            continue
        recent_posts_scanned += 1

        body = str(post.get("body", ""))
        score_result = score_post_for_catalyst(
            body,
            high_alert_threshold=high_alert_threshold,
            watch_threshold=watch_threshold,
            enable_aliases=enable_keyword_aliases,
        )
        post_score = int(score_result["total_score"])
        total_score += post_score

        if post_score > 0:
            triggered_posts.append(
                {
                    "id": post.get("id"),
                    "created_at": post.get("created_at"),
                    "body": body,
                    "keywords_found": score_result["keywords_found"],
                    "post_score": post_score,
                }
            )

    reason_code = "ok"
    if upstream_reason != "ok":
        reason_code = upstream_reason
    elif recent_posts_scanned == 0:
        reason_code = "no_recent_posts"
    elif total_score == 0:
        reason_code = "no_keywords_matched"

    return {
        "escalation_level": get_escalation_level(
            total_score,
            high_alert_threshold=high_alert_threshold,
            watch_threshold=watch_threshold,
        ),
        "total_score": total_score,
        "triggered_posts": triggered_posts,
        "posts_fetched": posts_fetched,
        "recent_posts_scanned": recent_posts_scanned,
        "posts_matched": len(triggered_posts),
        "reason_code": reason_code,
    }


def main() -> None:
    """
    Run a direct scanner demo for ticker AAPL.

    Inputs:
    - None.

    Output:
    - None. Prints scanner output in the terminal.

    Why this exists:
    - Direct execution is a quick smoke test for API reachability,
      response parsing, and keyword integration.
    """
    ticker = "AAPL"
    result = scan_ticker_social_signal(ticker=ticker, posts_to_fetch=30)
    print(f"Ticker: {ticker}")
    print(f"Escalation level: {result['escalation_level']}")
    print(f"Total score: {result['total_score']}")
    print(f"Triggered posts: {len(result['triggered_posts'])}")
    for item in result["triggered_posts"][:5]:
        print("-" * 80)
        print(f"Post ID: {item['id']}")
        print(f"Created: {item['created_at']}")
        print(f"Score: {item['post_score']}")
        print(f"Keywords: {item['keywords_found']}")
        print(f"Text: {item['body']}")


if __name__ == "__main__":
    main()

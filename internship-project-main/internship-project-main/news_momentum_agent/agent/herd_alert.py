"""Multi-source herd / HIGH_ALERT promotion.

Why multi-path exists
---------------------
Path A originally needed StockTwits HIGH_ALERT before news scoring ran. Quiet
but real catalysts (fresh wire + volume) never entered the decision pipeline
because social stayed IGNORE/WATCH. Promotion is now an **OR** of paths so
news-worthy names can reach HIGH_ALERT without waiting on social keywords.

HIGH_ALERT can be reached via ANY of:
  - stocktwits — existing keyword escalation
  - news_catalyst — fresh news with |score| >= threshold (scored at tagging time)
  - volume_spike — unusual Finviz RVol / price move (top decile of filtered set)

``require_social_signal`` is unchanged (still only blocks IGNORE downstream).
This module only tags; it does not execute trades.

Merge notes: fully reusable watchlist promotion pattern; no state files.
Path-specific thresholds live in ``settings.herd_alert``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_HERD_ALERT: Dict[str, Any] = {
    "enabled": True,
    "news_score_abs_min": 0.5,
    "news_max_age_hours": 4,
    "max_news_score_per_cycle": 6,
    "volume_rvol_percentile_min": 0.9,
    "volume_rvol_floor": 2.0,
    "volume_abs_pct_change_min": 1.0,
}


def herd_alert_config(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge ``settings.herd_alert`` onto default multi-path HIGH_ALERT thresholds."""
    cfg = dict(DEFAULT_HERD_ALERT)
    raw = (settings or {}).get("herd_alert")
    if isinstance(raw, dict):
        cfg.update(raw)
    return cfg


def _parse_iso_age_hours(published_at: Any, now: Optional[datetime] = None) -> Optional[float]:
    if published_at is None:
        return None
    text = str(published_at).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        return None


def news_catalyst_qualifies(
    score: Optional[float],
    published_at: Any = None,
    settings: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> bool:
    """True when news score magnitude and freshness meet herd-alert catalyst gates."""
    cfg = herd_alert_config(settings)
    if score is None:
        return False
    try:
        magnitude = abs(float(score))
    except (TypeError, ValueError):
        return False
    if magnitude < float(cfg.get("news_score_abs_min", 0.5)):
        return False
    max_age = float(cfg.get("news_max_age_hours", 4))
    age = _parse_iso_age_hours(published_at, now=now)
    if age is not None and age > max_age:
        return False
    return True


def _numeric_field_pairs(watchlist: Sequence[Dict[str, Any]], field: str) -> List[Tuple[int, float]]:
    pairs: List[Tuple[int, float]] = []
    for idx, stock in enumerate(watchlist):
        try:
            raw = stock.get(field)
            if raw is None:
                continue
            value = float(raw)
            if value > 0:
                pairs.append((idx, value))
        except (TypeError, ValueError):
            continue
    return pairs


def _percentile_ranks(pairs: List[Tuple[int, float]]) -> Dict[int, float]:
    if not pairs:
        return {}
    if len(pairs) == 1:
        return {pairs[0][0]: 1.0}
    ordered = sorted(pairs, key=lambda item: item[1])
    n = len(ordered)
    ranks: Dict[int, float] = {}
    for rank, (idx, _) in enumerate(ordered):
        ranks[idx] = rank / (n - 1)
    return ranks


def relative_volume_percentile_by_index(watchlist: Sequence[Dict[str, Any]]) -> Dict[int, float]:
    """
    Percentile rank in [0, 1] by relative_volume among stocks that have RVol.

    Falls back to absolute ``volume`` percentile when RVol/avg is missing
    (common on some Finviz scrape paths) so volume_spike still works on the
    filtered candidate set.
    """
    ranks = _percentile_ranks(_numeric_field_pairs(watchlist, "relative_volume"))
    if ranks:
        return ranks
    return _percentile_ranks(_numeric_field_pairs(watchlist, "volume"))


def volume_spike_qualifies(
    stock: Dict[str, Any],
    rvol_percentile: Optional[float],
    settings: Optional[Dict[str, Any]] = None,
) -> bool:
    """True when RVol percentile, floor, and price move clear volume_spike gates."""
    cfg = herd_alert_config(settings)
    if rvol_percentile is None:
        return False
    try:
        rvol = float(stock.get("relative_volume") or 0.0)
    except (TypeError, ValueError):
        rvol = 0.0
    try:
        pct = abs(float(stock.get("percent_change") or 0.0))
    except (TypeError, ValueError):
        pct = 0.0
    # When using absolute-volume fallback, skip the RVol floor (no avg available).
    using_rvol = stock.get("relative_volume") is not None
    if using_rvol and rvol < float(cfg.get("volume_rvol_floor", 2.0)):
        return False
    if pct < float(cfg.get("volume_abs_pct_change_min", 1.0)):
        return False
    return float(rvol_percentile) >= float(cfg.get("volume_rvol_percentile_min", 0.9))


def apply_multi_path_high_alert(
    watchlist: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
    *,
    news_by_ticker: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Mutate watchlist social_signal_level / alert_reason using OR of promotion paths.

    ``news_by_ticker`` maps TICKER → {"score": float, "published_at": optional}.
    StockTwits HIGH_ALERT already on the stock is preserved as path ``stocktwits``.
    WATCH from StockTwits is kept when no HIGH_ALERT path clears.

    ``alert_reason`` lists which path(s) fired — useful for debugging why a name
    entered the news/decision queue (and for Path A.2 / volume_spike audits).
    """
    cfg = herd_alert_config(settings)
    stats: Dict[str, Any] = {
        "enabled": bool(cfg.get("enabled", True)),
        "by_path": {"stocktwits": 0, "news_catalyst": 0, "volume_spike": 0},
        "high_alert_total": 0,
        "promoted_new": 0,
        "thresholds": {
            "news_score_abs_min": float(cfg.get("news_score_abs_min", 0.5)),
            "news_max_age_hours": float(cfg.get("news_max_age_hours", 4)),
            "volume_rvol_percentile_min": float(cfg.get("volume_rvol_percentile_min", 0.9)),
            "volume_rvol_floor": float(cfg.get("volume_rvol_floor", 2.0)),
            "volume_abs_pct_change_min": float(cfg.get("volume_abs_pct_change_min", 3.0)),
        },
    }
    if not stats["enabled"]:
        for stock in watchlist:
            level = str(stock.get("social_signal_level") or "IGNORE").upper()
            if level == "HIGH_ALERT":
                stock.setdefault("alert_reason", ["stocktwits"])
                stats["by_path"]["stocktwits"] += 1
                stats["high_alert_total"] += 1
        return stats

    news_map = news_by_ticker or {}
    rvol_ranks = relative_volume_percentile_by_index(watchlist)

    for idx, stock in enumerate(watchlist):
        ticker = str(stock.get("ticker") or "").upper()
        prior_level = str(stock.get("social_signal_level") or "IGNORE").upper()
        reasons: List[str] = []

        if prior_level == "HIGH_ALERT":
            reasons.append("stocktwits")

        news_meta = news_map.get(ticker) if ticker else None
        news_score = None
        published_at = None
        if isinstance(news_meta, dict):
            news_score = news_meta.get("score")
            published_at = news_meta.get("published_at")
        elif stock.get("herd_news_score") is not None:
            news_score = stock.get("herd_news_score")
            published_at = stock.get("herd_news_published_at") or stock.get("published_at")

        if news_catalyst_qualifies(news_score if news_score is None else float(news_score), published_at, settings):
            reasons.append("news_catalyst")
            stock["herd_news_score"] = float(news_score) if news_score is not None else None

        if volume_spike_qualifies(stock, rvol_ranks.get(idx), settings):
            reasons.append("volume_spike")
            stock["herd_rvol_percentile"] = rvol_ranks.get(idx)

        # Deduplicate while preserving order.
        deduped: List[str] = []
        for reason in reasons:
            if reason not in deduped:
                deduped.append(reason)

        if deduped:
            was_ha = prior_level == "HIGH_ALERT"
            stock["social_signal_level"] = "HIGH_ALERT"
            stock["alert_reason"] = deduped
            stats["high_alert_total"] += 1
            if not was_ha:
                stats["promoted_new"] += 1
            for reason in deduped:
                if reason in stats["by_path"]:
                    stats["by_path"][reason] += 1
        else:
            # Keep StockTwits WATCH / IGNORE; clear stale multi-path markers.
            stock.pop("alert_reason", None)
            if prior_level not in {"WATCH", "IGNORE", "HIGH_ALERT"}:
                stock["social_signal_level"] = "IGNORE"

    return stats


def collect_news_scores_for_watchlist(
    watchlist: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Score a capped set of watchlist names that have fresh wire/catalyst headlines.

    Used at tagging time so news_catalyst can promote without waiting for the
    separate HIGH_ALERT news job (which never runs when HA is zero).
    """
    cfg = herd_alert_config(settings)
    if not bool(cfg.get("enabled", True)):
        return {}

    max_score = max(0, int(cfg.get("max_news_score_per_cycle", 6)))
    if max_score <= 0:
        return {}

    universe = {
        str(stock.get("ticker") or "").upper()
        for stock in watchlist
        if stock.get("ticker")
    }
    if not universe:
        return {}

    try:
        from news.catalyst_scanner import scan_catalyst_headlines
    except Exception as error:
        print(f"[herd_alert] catalyst import failed: {error}")
        return {}

    try:
        hits = scan_catalyst_headlines(settings, universe=universe)
    except Exception as error:
        print(f"[herd_alert] catalyst scan failed: {error}")
        return {}

    # Prefer watchlist names that are not already StockTwits HIGH_ALERT.
    already_ha = {
        str(stock.get("ticker") or "").upper()
        for stock in watchlist
        if str(stock.get("social_signal_level") or "").upper() == "HIGH_ALERT"
    }
    ordered: List[Dict[str, Any]] = []
    seen: set = set()
    for hit in hits:
        ticker = str(hit.get("ticker") or "").upper()
        if not ticker or ticker in seen or ticker in already_ha:
            continue
        seen.add(ticker)
        ordered.append(hit)
        if len(ordered) >= max_score:
            break

    if not ordered:
        return {}

    try:
        from news.news_aggregator import aggregate_news_for_ticker
        from sentiment.claude_scorer import score_news_with_claude
        from sentiment.keyword_boost import apply_keyword_boost
    except Exception as error:
        print(f"[herd_alert] scorer import failed: {error}")
        return {}

    news_cfg = (settings or {}).get("news") or {}
    max_age = max(1, int(cfg.get("news_max_age_hours") or news_cfg.get("max_article_age_hours", 4)))
    article_chars = int(news_cfg.get("article_text_max_chars", 3000))
    scores: Dict[str, Dict[str, Any]] = {}

    for hit in ordered:
        ticker = str(hit.get("ticker") or "").upper()
        company = str(hit.get("company_name") or ticker)
        headline = str(hit.get("headline") or "").strip()
        source = str(hit.get("news_source") or hit.get("source") or "wire")
        published_at = hit.get("published_at")
        try:
            aggregated = aggregate_news_for_ticker(
                ticker=ticker,
                company_name=company,
                article_text_max_chars=article_chars,
                max_article_age_hours=max_age,
                settings=settings,
            )
            if not aggregated.get("has_news") and headline:
                try:
                    from news.solicitation_filter import is_law_firm_solicitation
                except Exception:
                    is_law_firm_solicitation = lambda *a, **k: False  # type: ignore
                if is_law_firm_solicitation(headline):
                    print(
                        f"[herd_alert] skipped solicitation for {ticker}: {headline[:80]}"
                    )
                    continue
                aggregated = {
                    "has_news": True,
                    "combined_text": (
                        f"[{source.upper()}]\nHeadline: {headline}\n"
                        "Text: Catalyst headline for herd-alert promotion.\n"
                    ),
                    "matched_articles": [
                        {"headline": headline, "source": source, "published_at": published_at}
                    ],
                }
            if not aggregated.get("has_news"):
                continue
            text = str(aggregated.get("combined_text") or "").strip()
            if not text:
                continue
            result = score_news_with_claude(ticker=ticker, news_text=text)
            score = apply_keyword_boost(
                base_score=float(result.get("score", 0.0)),
                news_text=text,
            )
            articles = aggregated.get("matched_articles") or []
            first = articles[0] if articles else {}
            scores[ticker] = {
                "score": float(score),
                "published_at": first.get("published_at") or published_at,
                "headline": first.get("headline") or headline,
            }
            print(
                f"[herd_alert] news score {ticker}: {score:+.2f} "
                f"(headline={(first.get('headline') or headline)[:60]!r})"
            )
        except Exception as error:
            print(f"[herd_alert] news score failed for {ticker}: {error}")
            continue

    return scores

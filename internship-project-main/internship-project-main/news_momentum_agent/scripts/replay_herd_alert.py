#!/usr/bin/env python3
"""Replay multi-path HIGH_ALERT promotion against tonight's live watchlist.

CLI
---
``python scripts/replay_herd_alert.py`` — reads ``state/watchlist.json``,
simulates ``apply_multi_path_high_alert``, writes markdown/JSON summary under
``state/``.

When to run
-----------
After a live watchlist cycle when tuning herd-alert thresholds; diagnostic only.

Safe vs live agent
------------------
**Safe:** Does not mutate live agent settings or restart ``main.py``. Writes
summary artifacts only; does not change ``high_alert.json`` unless code path
explicitly saves (review script — read-only promotion sim).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.herd_alert import apply_multi_path_high_alert, herd_alert_config  # noqa: E402


def main() -> int:
    """Replay multi-path HIGH_ALERT on live watchlist; write JSON/MD summary under state/."""
    settings = json.loads((PROJECT_ROOT / "settings.json").read_text(encoding="utf-8"))
    watch_path = PROJECT_ROOT / "state" / "watchlist.json"
    if not watch_path.exists():
        print("No state/watchlist.json — run the agent first.")
        return 1
    payload = json.loads(watch_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        print("watchlist.json has no items list")
        return 1

    # Snapshot social tags before promotion (StockTwits-only baseline).
    before_ha = sum(
        1 for s in items if str(s.get("social_signal_level") or "").upper() == "HIGH_ALERT"
    )
    before_watch = sum(
        1 for s in items if str(s.get("social_signal_level") or "").upper() == "WATCH"
    )

    # Replay without live news scoring (volume + existing stocktwits only), then
    # optionally include any herd_news_score already stamped on rows.
    rows = [dict(s) for s in items]
    news_by_ticker = {}
    for s in rows:
        ticker = str(s.get("ticker") or "").upper()
        if s.get("herd_news_score") is not None:
            news_by_ticker[ticker] = {
                "score": s.get("herd_news_score"),
                "published_at": s.get("herd_news_published_at") or s.get("published_at"),
            }

    stats = apply_multi_path_high_alert(rows, settings, news_by_ticker=news_by_ticker)
    promoted = [
        {
            "ticker": r.get("ticker"),
            "alert_reason": r.get("alert_reason"),
            "relative_volume": r.get("relative_volume"),
            "percent_change": r.get("percent_change"),
            "herd_rvol_percentile": r.get("herd_rvol_percentile"),
            "prior_would_be_stocktwits_only": str(
                next(
                    (x.get("social_signal_level") for x in items if x.get("ticker") == r.get("ticker")),
                    "IGNORE",
                )
            ).upper()
            == "HIGH_ALERT",
        }
        for r in rows
        if str(r.get("social_signal_level") or "").upper() == "HIGH_ALERT"
    ]
    volume_only = [p for p in promoted if p["alert_reason"] == ["volume_spike"]]
    news_only = [p for p in promoted if "news_catalyst" in (p["alert_reason"] or [])]

    cfg = herd_alert_config(settings)
    day = datetime.now(timezone.utc).date().isoformat()
    out = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "watchlist_n": len(items),
        "before": {"HIGH_ALERT": before_ha, "WATCH": before_watch},
        "after": {
            "HIGH_ALERT": stats.get("high_alert_total"),
            "by_path": stats.get("by_path"),
            "promoted_new": stats.get("promoted_new"),
        },
        "thresholds": cfg,
        "promoted": promoted,
        "note": (
            "Replay uses live watchlist Finviz+StockTwits fields. "
            "News path only includes scores already stamped on rows unless "
            "collect_news_scores_for_watchlist is run live in the agent cycle."
        ),
    }
    state_dir = PROJECT_ROOT / "state"
    json_path = state_dir / f"herd_alert_replay_{day}.json"
    md_path = state_dir / f"herd_alert_replay_{day}.md"
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "# Multi-path HIGH_ALERT replay (tonight's watchlist)",
        "",
        f"- Watchlist size: **{len(items)}**",
        f"- Before (StockTwits-only tags on file): HIGH_ALERT=**{before_ha}**, WATCH=**{before_watch}**",
        f"- After multi-path: HIGH_ALERT=**{stats.get('high_alert_total')}** "
        f"`by_path={stats.get('by_path')}` promoted_new=**{stats.get('promoted_new')}**",
        f"- Volume-only promotions: **{len(volume_only)}**",
        f"- News-path promotions (pre-stamped scores only in this offline replay): **{len(news_only)}**",
        "",
        "## Thresholds",
        "",
        f"```json\n{json.dumps(cfg, indent=2)}\n```",
        "",
        "## Promoted names",
        "",
    ]
    for p in promoted:
        lines.append(
            f"- `{p['ticker']}` reasons=`{p['alert_reason']}` "
            f"rvol=`{p.get('relative_volume')}` pct=`{p.get('percent_change')}` "
            f"rvol_pctile=`{p.get('herd_rvol_percentile')}`"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(out["after"], indent=2))
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compact nflverse schedule text for Gemini context (no extra HTTP — uses cached schedules)."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from app.nflverse_schedules import get_schedules_dataframe


def default_nfl_season_year() -> int:
    today = date.today()
    if today.month >= 8:
        return today.year
    return today.year - 1


def build_nflverse_schedule_context(user_message: str, season: int | None = None, max_chars: int = 4500) -> str:
    """Human-readable snapshot: league averages, leaders, optional team focus from abbreviations in the message."""
    if season is None:
        season = default_nfl_season_year()

    try:
        full = get_schedules_dataframe()
    except Exception as e:
        return f"## nflverse schedule data\nFetch failed ({e}). Do not invent team records or scores."

    lines: list[str] = []
    df = pd.DataFrame()
    used_season = season
    for sy in (season, season - 1, season - 2):
        cand = full[(full["season"] == sy) & (full["game_type"] == "REG")].copy()
        if not cand.empty:
            df = cand
            used_season = int(sy)
            break

    if df.empty:
        return f"## nflverse schedule data\nNo regular-season schedule rows for {season} (or prior seasons in cache)."

    has_scores = df["home_score"].notna() & df["away_score"].notna()
    finished = df[has_scores].copy()

    lines.append(f"## nflverse schedule snapshot ({used_season} REG)")
    lines.append(f"- Schedule rows: {len(df)}; games with scores in data: {len(finished)}.")

    teams = sorted(set(df["home_team"].dropna().astype(str)) | set(df["away_team"].dropna().astype(str)))
    msg_upper = user_message.upper()

    if len(finished):
        hc = pd.to_numeric(finished["home_score"], errors="coerce")
        ac = pd.to_numeric(finished["away_score"], errors="coerce")
        combined = hc + ac
        lines.append(f"- Mean combined score (finished games): {combined.mean():.2f} pts.")

        hi = combined.idxmax()
        r = finished.loc[hi]
        lines.append(
            f"- Highest combined score: {r['away_team']} @ {r['home_team']} "
            f"W{int(r['week'])} ({int(r['away_score'])}-{int(r['home_score'])})."
        )

        stats: dict[str, dict[str, float]] = {}
        for t in teams:
            hr = finished[finished["home_team"] == t]
            ar = finished[finished["away_team"] == t]
            gp = len(hr) + len(ar)
            if gp == 0:
                continue
            pf = float(hr["home_score"].astype(float).sum() + ar["away_score"].astype(float).sum())
            pa = float(hr["away_score"].astype(float).sum() + ar["home_score"].astype(float).sum())
            wins = float((hr["home_score"].astype(float) > hr["away_score"].astype(float)).sum())
            wins += float((ar["away_score"].astype(float) > ar["home_score"].astype(float)).sum())
            stats[t] = {"gp": gp, "wins": wins, "pf": pf, "pa": pa, "ppg": pf / gp, "papg": pa / gp}

        ranked = sorted(stats.items(), key=lambda kv: -kv[1]["ppg"])
        lines.append("\n### Offenses by PPG (finished games, min 3 GP)")
        for t, s in ranked[:10]:
            if s["gp"] < 3:
                continue
            losses = int(s["gp"] - s["wins"])
            lines.append(
                f"- {t}: {s['ppg']:.1f} PPG / {s['papg']:.1f} PAPG — {int(s['wins'])}-{losses} (W-L in scored games)"
            )

        mentioned: list[str] = []
        for t in teams:
            if re.search(rf"\b{re.escape(t)}\b", msg_upper):
                mentioned.append(t)
        mentioned = mentioned[:4]
        if mentioned:
            lines.append("\n### User-mentioned teams (abbreviations detected)")
            for t in mentioned:
                s = stats.get(t)
                if not s:
                    lines.append(f"- {t}: no finished games in dataset yet.")
                    continue
                losses = int(s["gp"] - s["wins"])
                lines.append(
                    f"- {t}: {s['ppg']:.1f} PPG, {s['papg']:.1f} PAPG, {int(s['wins'])}-{losses} (scored games only)"
                )

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…(truncated)"
    return text

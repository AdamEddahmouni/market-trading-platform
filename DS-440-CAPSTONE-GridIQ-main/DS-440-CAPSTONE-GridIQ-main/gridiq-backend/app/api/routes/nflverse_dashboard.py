"""Read-only nflverse data for the dashboard (nflverse GitHub releases)."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.nflverse_pbp_store import load_season_frame
from app.nflverse_schedules import allowed_nflverse_seasons, get_schedules_dataframe

router = APIRouter()

_SEASON_MSG = "Change NFLVERSE_SEASONS in gridiq-backend/.env and restart the API."


def _cell_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.floating,)):
        x = float(v)
        return None if math.isnan(x) else x
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _schedule_row_dict(row: pd.Series) -> dict[str, Any]:
    gd = row.get("gameday")
    if gd is None or pd.isna(gd):
        gameday_str = None
    elif hasattr(gd, "isoformat"):
        gameday_str = gd.isoformat()
    else:
        gameday_str = str(gd)

    def num(x: Any) -> float | None:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    return {
        "gameId": str(row["game_id"]),
        "season": int(row["season"]),
        "gameType": str(row["game_type"]),
        "week": int(row["week"]),
        "gameday": gameday_str,
        "weekday": None if pd.isna(row.get("weekday")) else str(row["weekday"]),
        "gametime": None if pd.isna(row.get("gametime")) else str(row["gametime"]),
        "awayTeam": str(row["away_team"]),
        "homeTeam": str(row["home_team"]),
        "awayScore": num(row.get("away_score")),
        "homeScore": num(row.get("home_score")),
        "stadium": None if pd.isna(row.get("stadium")) else str(row["stadium"]),
    }


def _play_row_dict(row: pd.Series) -> dict[str, Any]:
    pid = row.get("play_id")
    play_id = str(int(pid)) if pd.notna(pid) and not isinstance(pid, str) else (str(pid) if pid is not None else "")

    down = row.get("down")
    ytg = row.get("ydstogo")

    return {
        "id": play_id,
        "gameId": str(row["game_id"]),
        "quarter": None if pd.isna(row.get("qtr")) else int(row["qtr"]),
        "down": None if pd.isna(down) else int(down),
        "yardsToGo": None if pd.isna(ytg) else int(ytg),
        "playType": None if pd.isna(row.get("play_type")) else str(row["play_type"]),
        "description": None if pd.isna(row.get("desc")) else str(row["desc"]),
        "offense": None if pd.isna(row.get("posteam")) else str(row["posteam"]),
        "defense": None if pd.isna(row.get("defteam")) else str(row["defteam"]),
        "epa": _cell_json(row.get("epa")),
        "yardsGained": _cell_json(row.get("yards_gained")),
    }


def _season_from_game_id(game_id: str) -> int:
    parts = game_id.split("_")
    if len(parts) < 1 or not parts[0].isdigit():
        raise HTTPException(status_code=400, detail="Invalid game_id format")
    return int(parts[0])


def _teams_from_game_id(game_id: str) -> tuple[str, str]:
    """Return (away_team, home_team) from nflverse game_id, e.g. 2024_01_DET_KC."""
    parts = game_id.split("_")
    if len(parts) >= 4 and all(p.isalpha() for p in parts[-2:]):
        return str(parts[-2]), str(parts[-1])
    raise HTTPException(status_code=400, detail="Cannot parse teams from game_id")


def _numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _quarterly_scoring(sub: pd.DataFrame) -> list[dict[str, Any]]:
    df = sub.sort_values("play_id")
    if "total_home_score" not in df.columns or df["total_home_score"].isna().all():
        return []
    th = _numeric_series(df["total_home_score"]).tolist()
    ta = _numeric_series(df["total_away_score"]).tolist()
    qtrs = df["qtr"].tolist()
    prev_h, prev_a = 0.0, 0.0
    out: list[dict[str, Any]] = []
    max_q = int(pd.to_numeric(df["qtr"], errors="coerce").max()) if df["qtr"].notna().any() else 0
    for q in range(1, max_q + 1):
        idx = [i for i in range(len(df)) if qtrs[i] == q]
        if not idx:
            cum_h, cum_a = prev_h, prev_a
        else:
            i = idx[-1]
            cum_h, cum_a = float(th[i]), float(ta[i])
        out.append(
            {
                "quarter": q,
                "homePoints": round(cum_h - prev_h, 3),
                "awayPoints": round(cum_a - prev_a, 3),
                "homeCumulative": cum_h,
                "awayCumulative": cum_a,
            }
        )
        prev_h, prev_a = cum_h, cum_a
    return out


def _top_rusher_team(df: pd.DataFrame, team: str) -> dict[str, Any] | None:
    run = df[(df["play_type"] == "run") & (df["posteam"] == team)].copy()
    run = run[run["rusher_player_name"].notna() & (run["rusher_player_name"].astype(str).str.len() > 0)]
    if run.empty:
        return None
    yds = _numeric_series(run["yards_gained"])
    run["_y"] = yds
    g = run.groupby("rusher_player_name", dropna=True).agg(yards=("_y", "sum"), carries=("play_id", "count"))
    top = g.sort_values(["yards", "carries"], ascending=False).iloc[0]
    return {"name": str(top.name), "yards": int(top["yards"]), "carries": int(top["carries"])}


def _top_receiver_team(df: pd.DataFrame, team: str) -> dict[str, Any] | None:
    p = df[(df["play_type"] == "pass") & (df["posteam"] == team)].copy()
    p = p[p["receiver_player_name"].notna() & (p["receiver_player_name"].astype(str).str.len() > 0)]
    if p.empty:
        return None
    p["_y"] = _numeric_series(p["yards_gained"])
    if "complete_pass" in p.columns:
        p["_c"] = _numeric_series(p["complete_pass"])
    else:
        p["_c"] = 0
    g = p.groupby("receiver_player_name", dropna=True).agg(
        yards=("_y", "sum"),
        receptions=("_c", "sum"),
    )
    top = g.sort_values(["yards", "receptions"], ascending=False).iloc[0]
    return {"name": str(top.name), "yards": int(top["yards"]), "receptions": int(top["receptions"])}


def _top_passer_team(df: pd.DataFrame, team: str) -> dict[str, Any] | None:
    p = df[(df["play_type"] == "pass") & (df["posteam"] == team)].copy()
    p = p[p["passer_player_name"].notna() & (p["passer_player_name"].astype(str).str.len() > 0)]
    if p.empty:
        return None
    p["_y"] = _numeric_series(p["yards_gained"])
    if "pass_touchdown" in p.columns:
        p["_td"] = _numeric_series(p["pass_touchdown"])
    elif "touchdown" in p.columns:
        p["_td"] = _numeric_series(p["touchdown"])
    else:
        p["_td"] = 0
    p["_int"] = _numeric_series(p["interception"]) if "interception" in p.columns else 0
    g = p.groupby("passer_player_name", dropna=True).agg(
        yards=("_y", "sum"),
        touchdowns=("_td", "sum"),
        interceptions=("_int", "sum"),
    )
    top = g.sort_values(["yards", "touchdowns"], ascending=False).iloc[0]
    return {
        "name": str(top.name),
        "yards": int(top["yards"]),
        "touchdowns": int(top["touchdowns"]),
        "interceptions": int(top["interceptions"]),
    }


def _field_goals_team(df: pd.DataFrame, team: str) -> dict[str, int]:
    fg = df[(df["play_type"] == "field_goal") & (df["posteam"] == team)]
    if fg.empty or "field_goal_result" not in fg.columns:
        return {"made": 0, "missed": 0, "attempted": 0}
    res = fg["field_goal_result"].astype(str).str.lower()
    made = int((res == "made").sum())
    missed = int(res.isin(["missed", "blocked"]).sum())
    return {"made": made, "missed": missed, "attempted": int(len(fg))}


def _fumbles_team(df: pd.DataFrame, team: str) -> dict[str, int]:
    t = df[df["posteam"] == team]
    if t.empty:
        return {"playsWithFumble": 0, "lost": 0}
    fum = t["fumble"] if "fumble" in t.columns else pd.Series(0, index=t.index)
    fl = t["fumble_lost"] if "fumble_lost" in t.columns else pd.Series(0, index=t.index)
    fu = _numeric_series(fum) > 0
    lost = _numeric_series(fl) > 0
    return {"playsWithFumble": int(fu.sum()), "lost": int(lost.sum())}


def _scoring_highlights(sub: pd.DataFrame, *, limit: int = 12) -> list[dict[str, Any]]:
    df = sub.sort_values("play_id")
    td_col = df["touchdown"] if "touchdown" in df.columns else pd.Series(0, index=df.index)
    mask_td = _numeric_series(td_col) > 0
    mask_fg = pd.Series(False, index=df.index)
    if "field_goal_result" in df.columns:
        mask_fg = df["field_goal_result"].astype(str).str.lower() == "made"
    sel = df[mask_td | mask_fg].head(limit)
    rows: list[dict[str, Any]] = []
    for _, row in sel.iterrows():
        name = None
        is_td = float(row["touchdown"]) > 0 if "touchdown" in row.index and pd.notna(row.get("touchdown")) else False
        if is_td:
            pt = (
                float(row["pass_touchdown"])
                if "pass_touchdown" in row.index and pd.notna(row.get("pass_touchdown"))
                else 0.0
            )
            rt = (
                float(row["rush_touchdown"])
                if "rush_touchdown" in row.index and pd.notna(row.get("rush_touchdown"))
                else 0.0
            )
            if pt > 0 and pd.notna(row.get("receiver_player_name")):
                name = str(row["receiver_player_name"])
            elif rt > 0 and pd.notna(row.get("rusher_player_name")):
                name = str(row["rusher_player_name"])
            elif pd.notna(row.get("rusher_player_name")):
                name = str(row["rusher_player_name"])
            elif pd.notna(row.get("receiver_player_name")):
                name = str(row["receiver_player_name"])
        rows.append(
            {
                "quarter": None if pd.isna(row.get("qtr")) else int(row["qtr"]),
                "playType": None if pd.isna(row.get("play_type")) else str(row["play_type"]),
                "team": None if pd.isna(row.get("posteam")) else str(row["posteam"]),
                "player": name,
                "description": None if pd.isna(row.get("desc")) else str(row["desc"])[:240],
            }
        )
    return rows


def _game_summary_dict(game_id: str, sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        raise HTTPException(status_code=404, detail="No plays for game")
    sub = sub.copy()
    away_parsed, home_parsed = _teams_from_game_id(game_id)
    ht_row = sub.iloc[0].get("home_team")
    at_row = sub.iloc[0].get("away_team")
    home_team = str(ht_row) if pd.notna(ht_row) and str(ht_row).strip() else home_parsed
    away_team = str(at_row) if pd.notna(at_row) and str(at_row).strip() else away_parsed

    last = sub.sort_values("play_id").iloc[-1]
    home_score = _cell_json(last.get("total_home_score"))
    away_score = _cell_json(last.get("total_away_score"))

    return {
        "gameId": game_id,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "homeScore": home_score,
        "awayScore": away_score,
        "quarterlyScores": _quarterly_scoring(sub),
        "highlights": _scoring_highlights(sub),
        "topRusherByTeam": {
            "home": _top_rusher_team(sub, home_team),
            "away": _top_rusher_team(sub, away_team),
        },
        "topReceiverByTeam": {
            "home": _top_receiver_team(sub, home_team),
            "away": _top_receiver_team(sub, away_team),
        },
        "topPasserByTeam": {
            "home": _top_passer_team(sub, home_team),
            "away": _top_passer_team(sub, away_team),
        },
        "fieldGoalsByTeam": {
            "home": _field_goals_team(sub, home_team),
            "away": _field_goals_team(sub, away_team),
        },
        "fumblesByTeam": {
            "home": _fumbles_team(sub, home_team),
            "away": _fumbles_team(sub, away_team),
        },
    }


@router.get("/nflverse/schedule")
def nflverse_schedule(
    season: int = Query(..., ge=1999, le=2035, description="NFL season year"),
    week: int | None = Query(None, ge=1, le=22, description="Restrict to a single week"),
    game_type: str = Query("REG", description="REG, POST, or ALL"),
):
    """Regular-season (or postseason) schedule from nflverse."""
    allowed = allowed_nflverse_seasons()
    if season not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Season {season} is not loaded. Allowed: {sorted(allowed)}. {_SEASON_MSG}",
        )
    try:
        df = get_schedules_dataframe()
        df = df.loc[df["season"] == season].copy()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to download nflverse schedules from GitHub. "
                "Check network / firewall / SSL. "
                f"Underlying error: {e}"
            ),
        ) from e

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule rows found for season {season}. Try another year.",
        )

    if game_type.upper() != "ALL":
        gt = game_type.upper()
        df = df[df["game_type"] == gt]
    if week is not None:
        df = df[df["week"] == week]

    df = df.sort_values(["week", "gameday", "gametime", "game_id"], na_position="last")
    games = [_schedule_row_dict(row) for _, row in df.iterrows()]
    return {"season": season, "source": "nflverse", "games": games}


@router.get("/nflverse/games/{game_id}/plays")
def nflverse_game_plays(
    game_id: str,
    limit: int = Query(250, ge=1, le=500),
):
    """Play-by-play for one game (nflverse game_id), e.g. 2023_01_DET_KC."""
    season = _season_from_game_id(game_id)
    if season not in allowed_nflverse_seasons():
        raise HTTPException(
            status_code=400,
            detail=f"PBP for season {season} is not loaded. Allowed: {sorted(allowed_nflverse_seasons())}. {_SEASON_MSG}",
        )

    try:
        frame = load_season_frame(season)
        sub = frame[frame["game_id"] == game_id]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to load nflverse play-by-play: {e}") from e

    if sub.empty:
        raise HTTPException(status_code=404, detail="Game not found in play-by-play for that season")

    sub = sub.head(limit)
    plays = [_play_row_dict(row) for _, row in sub.iterrows()]
    return {"gameId": game_id, "source": "nflverse", "plays": plays}


@router.get("/nflverse/games/{game_id}/summary")
def nflverse_game_summary(game_id: str):
    """Aggregated box-score style stats for one game (full PBP slice; no play limit)."""
    season = _season_from_game_id(game_id)
    if season not in allowed_nflverse_seasons():
        raise HTTPException(
            status_code=400,
            detail=f"PBP for season {season} is not loaded. Allowed: {sorted(allowed_nflverse_seasons())}. {_SEASON_MSG}",
        )

    try:
        frame = load_season_frame(season)
        sub = frame[frame["game_id"] == game_id]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to load nflverse play-by-play: {e}") from e

    summary = _game_summary_dict(game_id, sub)
    return {"source": "nflverse", **summary}

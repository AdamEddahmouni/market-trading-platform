"""Shared in-memory nflverse play-by-play parquet cache (dashboard + chat)."""

from __future__ import annotations

from collections import OrderedDict

import numpy as np
import pandas as pd

from app.nflverse_parquet import read_parquet_from_url_fill_columns
from app.nflverse_schedules import allowed_nflverse_seasons

_PBP_PARQUET_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
)

PBP_COLS = [
    "play_id",
    "game_id",
    "week",
    "qtr",
    "down",
    "ydstogo",
    "play_type",
    "desc",
    "posteam",
    "defteam",
    "home_team",
    "away_team",
    "epa",
    "yards_gained",
    "passer_player_name",
    "rusher_player_name",
    "receiver_player_name",
    "complete_pass",
    "pass_touchdown",
    "rush_touchdown",
    "touchdown",
    "interception",
    "fumble",
    "fumble_lost",
    "field_goal_result",
    "total_home_score",
    "total_away_score",
]

_season_frames: OrderedDict[int, pd.DataFrame] = OrderedDict()


def load_season_frame(season: int) -> pd.DataFrame:
    """Load and cache PBP for one season (only if that year is in ``NFLVERSE_SEASONS``)."""
    if season not in allowed_nflverse_seasons():
        return pd.DataFrame()

    if season in _season_frames:
        _season_frames.move_to_end(season)
        return _season_frames[season]

    url = _PBP_PARQUET_URL.format(season=season)
    df = read_parquet_from_url_fill_columns(url, columns=PBP_COLS, timeout_sec=300)
    if df.empty:
        _season_frames[season] = df
    else:
        f64 = df.select_dtypes(include=[np.float64]).columns
        if len(f64) > 0:
            df = df.copy()
            df[f64] = df[f64].astype(np.float32)
        _season_frames[season] = df

    cap = max(1, len(allowed_nflverse_seasons()))
    while len(_season_frames) > cap:
        _season_frames.popitem(last=False)

    return _season_frames[season]


def plays_for_game_sorted(game_id: str) -> pd.DataFrame:
    """All plays for one nflverse game_id, sorted by play_id."""
    parts = game_id.split("_")
    if len(parts) < 1 or not parts[0].isdigit():
        return pd.DataFrame()
    season = int(parts[0])
    frame = load_season_frame(season)
    if frame.empty or "game_id" not in frame.columns:
        return pd.DataFrame()
    sub = frame[frame["game_id"] == game_id].copy()
    if sub.empty:
        return sub
    return sub.sort_values("play_id")

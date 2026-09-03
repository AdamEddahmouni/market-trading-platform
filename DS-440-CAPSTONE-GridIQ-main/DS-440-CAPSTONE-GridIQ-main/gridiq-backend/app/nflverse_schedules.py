"""nflverse schedules via HTTPS (avoids nfl_data_py's HTTP habitatring.com source)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.nflverse_parquet import read_parquet_from_url

SCHEDULES_PARQUET_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.parquet"
)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SCHEDULE_CACHE_PATH = _BACKEND_ROOT / ".cache" / "nflverse" / "games.parquet"

_schedule_df: pd.DataFrame | None = None


def nflverse_wanted_seasons() -> frozenset[int]:
    """Configured NFL season years (from ``NFLVERSE_SEASONS``). Invalid tokens skipped."""
    raw = (settings.NFLVERSE_SEASONS or "").strip()
    out: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p.isdigit():
            continue
        y = int(p)
        if 1999 <= y <= 2100:
            out.append(y)
    return frozenset(out) if out else frozenset({2025})


def _trim_to_wanted_seasons(df: pd.DataFrame) -> pd.DataFrame:
    want = nflverse_wanted_seasons()
    if "season" not in df.columns:
        return df
    return df.loc[df["season"].isin(want)].copy()


def get_schedules_dataframe() -> pd.DataFrame:
    """Schedules limited to ``NFLVERSE_SEASONS``; in-process + disk cache."""
    global _schedule_df
    if _schedule_df is None:
        raw: pd.DataFrame | None = None
        try:
            raw = read_parquet_from_url(SCHEDULES_PARQUET_URL, timeout_sec=120)
        except Exception:
            if _SCHEDULE_CACHE_PATH.is_file():
                raw = pd.read_parquet(_SCHEDULE_CACHE_PATH)
            else:
                raise
        _schedule_df = _trim_to_wanted_seasons(raw)
        del raw
        try:
            _SCHEDULE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _schedule_df.to_parquet(_SCHEDULE_CACHE_PATH, index=False)
        except Exception:
            pass
    return _schedule_df


def allowed_nflverse_seasons() -> frozenset[int]:
    """Season years currently available after trimming."""
    df = get_schedules_dataframe()
    return frozenset(int(x) for x in df["season"].dropna().unique())

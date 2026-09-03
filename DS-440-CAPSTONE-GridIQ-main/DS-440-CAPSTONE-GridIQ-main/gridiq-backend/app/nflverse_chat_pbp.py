"""Optional nflverse play-by-play context for chat: resolve game from transcript, attach plays or instruct model to clarify."""

from __future__ import annotations

import math
import re

import pandas as pd

from app.nflverse_chat_context import default_nfl_season_year
from app.nflverse_pbp_store import plays_for_game_sorted
from app.nflverse_schedules import get_schedules_dataframe

_GAME_ID_RE = re.compile(r"\b(20\d{2}_\d{1,2}_[A-Z]{2,3}_[A-Z]{2,3})\b")
_WEEK_RE = re.compile(r"\b(?:week|wk)\s*(\d{1,2})\b", re.IGNORECASE)

_PBP_TRIGGERS = (
    "play-by-play",
    "play by play",
    "playbyplay",
    "pbp",
    "every play",
    "each play",
    "snap by snap",
    "drive by drive",
    "drive-by-drive",
    "walk me through",
    "break down the game",
    "in depth",
    "in-depth",
    "detailed plays",
    "all the plays",
    "full game",
    "every snap",
)


def user_wants_play_by_play(transcript_lower: str) -> bool:
    return any(t in transcript_lower for t in _PBP_TRIGGERS)


def _schedule_reg_dataframe() -> tuple[pd.DataFrame, int]:
    """Regular-season schedule slice (same season preference as schedule snapshot)."""
    season = default_nfl_season_year()
    full = get_schedules_dataframe()
    for sy in (season, season - 1, season - 2):
        cand = full[(full["season"] == sy) & (full["game_type"] == "REG")].copy()
        if not cand.empty:
            return cand, int(sy)
    return pd.DataFrame(), season


def _teams_mentioned(text_upper: str, teams: list[str]) -> list[str]:
    found: list[str] = []
    for t in teams:
        if re.search(rf"\b{re.escape(t)}\b", text_upper):
            found.append(t)
    return found


def resolve_nflverse_game_id(transcript: str) -> tuple[str | None, str]:
    """
    Return (game_id, note). game_id set when uniquely resolved.
    note is non-empty for model hints (ambiguous / invalid id).
    """
    schedule, _used_season = _schedule_reg_dataframe()
    if schedule.empty or "game_id" not in schedule.columns:
        return None, "Schedule data unavailable; cannot resolve a game_id."

    gid_set = set(schedule["game_id"].astype(str))

    m = _GAME_ID_RE.search(transcript)
    if m:
        gid = m.group(1)
        if gid in gid_set:
            return gid, ""
        return None, f"The message cites game_id `{gid}`, which is not in the current schedule slice."

    teams = sorted(set(schedule["home_team"].dropna().astype(str)) | set(schedule["away_team"].dropna().astype(str)))
    text_upper = transcript.upper()

    season_m = re.search(r"\b(20\d{2})\b", transcript)
    sub = schedule
    if season_m:
        sy = int(season_m.group(1))
        sub = sub[sub["season"] == sy]
        if sub.empty:
            return None, f"No schedule rows for season {sy} to match against."

    week_m = _WEEK_RE.search(transcript)
    week = int(week_m.group(1)) if week_m else None
    if week is not None:
        sub = sub[sub["week"] == week]

    mentioned = _teams_mentioned(text_upper, teams)

    if len(mentioned) >= 2:
        t1, t2 = mentioned[0], mentioned[1]
        cand = sub[
            ((sub["away_team"] == t1) & (sub["home_team"] == t2))
            | ((sub["away_team"] == t2) & (sub["home_team"] == t1))
        ]
        if len(cand) == 1:
            return str(cand.iloc[0]["game_id"]), ""
        if len(cand) > 1:
            return (
                None,
                f"Multiple games match {t1} vs {t2}"
                f"{f' in week {week}' if week is not None else ''}. Ask which week or season.",
            )
    if len(mentioned) == 1 and week is not None:
        t = mentioned[0]
        cand = sub[(sub["away_team"] == t) | (sub["home_team"] == t)]
        if len(cand) == 1:
            return str(cand.iloc[0]["game_id"]), ""
        if len(cand) > 1:
            return None, f"Several games in week {week} involve {t}. Ask which opponent (away @ home)."

    return None, ""


def _fmt_play_row(row: pd.Series) -> str:
    q = row.get("qtr")
    down = row.get("down")
    ytg = row.get("ydstogo")
    dd = ""
    if pd.notna(down) and pd.notna(ytg):
        dd = f"{int(down)} & {int(ytg)}"
    pt = row.get("play_type")
    off = row.get("posteam")
    epa = row.get("epa")
    yds = row.get("yards_gained")
    desc = row.get("desc")
    desc = "" if pd.isna(desc) else str(desc)
    desc = desc.replace("\n", " ")[:220]
    epa_s = ""
    if isinstance(epa, (int, float)) and not (isinstance(epa, float) and math.isnan(epa)):
        epa_s = f" EPA {float(epa):.2f}"
    yds_s = ""
    if isinstance(yds, (int, float)) and not (isinstance(yds, float) and math.isnan(yds)):
        yds_s = f" {int(yds)} yd"
    q_s = "?" if pd.isna(q) else f"Q{int(q)}"
    return (
        f"- {q_s} {dd} | {off} | {pt}{yds_s}{epa_s} | {desc}"
        .replace("  ", " ")
    )


def format_plays_for_llm(game_id: str, max_chars: int = 18_000) -> str:
    """Format full game PBP for model context; cap size."""
    df = plays_for_game_sorted(game_id)
    if df.empty:
        return f"(No play-by-play rows found for game_id `{game_id}`.)"

    lines = [
        f"## Attached play-by-play (nflverse) — game_id `{game_id}`",
        f"- Plays in slice: {len(df)} (truncated if this section hits char limit)",
        "",
    ]
    buf = "\n".join(lines)
    for _, row in df.iterrows():
        line = _fmt_play_row(row) + "\n"
        if len(buf) + len(line) > max_chars:
            buf += "\n…(remaining plays omitted for length)\n"
            break
        buf += line
    return buf


def build_optional_play_by_play_section(transcript: str, latest_user_message: str) -> str:
    """
    Extra model context only: schedule resolution + optional PBP text.
    No API changes — assembled in chat route.
    """
    transcript_lower = transcript.lower()
    wants = user_wants_play_by_play(transcript_lower)
    explicit_id = _GAME_ID_RE.search(latest_user_message) is not None or _GAME_ID_RE.search(transcript) is not None

    if not wants and not explicit_id:
        return ""

    gid, note = resolve_nflverse_game_id(transcript)

    if gid and (wants or explicit_id):
        try:
            return format_plays_for_llm(gid)
        except Exception as e:
            return (
                "## Play-by-play\n"
                f"Resolved game_id `{gid}` but loading plays failed: {e}. "
                "Answer from general knowledge only for this game; do not invent plays."
            )

    if wants:
        lines = [
            "## Play-by-play",
            "The user asked for detailed play-by-play, but **no single game was resolved** from the conversation.",
            "**You must ask concise clarifying questions** before describing specific plays:",
            "- NFL **season** year (e.g. 2024), **week** number, and **both teams** (away @ home), **or**",
            "- The exact **nflverse game_id** (format like `2024_14_BUF_KC`).",
        ]
        if note:
            lines.append(f"Resolver note: {note}")
        lines.append("Do **not** invent or guess play-by-play for a game you did not identify.")
        return "\n".join(lines)

    if explicit_id and note:
        return "## Play-by-play\n" + note + "\nAsk the user to confirm the game if needed."

    return ""

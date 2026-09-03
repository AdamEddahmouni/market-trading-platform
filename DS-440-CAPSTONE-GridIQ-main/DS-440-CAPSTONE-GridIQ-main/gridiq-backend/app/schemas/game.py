from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PlaySchema(BaseModel):
    id: str
    game_id: str
    play_id: str
    quarter: int
    minute: Optional[int] = None
    second: Optional[int] = None
    posteam: Optional[str] = None
    defteam: Optional[str] = None
    play_description: Optional[str] = None
    play_type: Optional[str] = None
    yards_gained: Optional[int] = None
    yards_to_go: Optional[int] = None
    down: Optional[int] = None
    epa: Optional[float] = None
    wpa: Optional[float] = None
    air_yards: Optional[float] = None
    yards_after_catch: Optional[float] = None
    touchdown: Optional[bool] = None
    interception: Optional[bool] = None
    fumble: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GameSchema(BaseModel):
    id: str
    game_id: str
    season: int
    week: int
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    game_date: datetime
    stadium: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GameDetailSchema(GameSchema):
    plays: list[PlaySchema] = []


class GameFilterSchema(BaseModel):
    season: Optional[int] = Field(None, description="NFL season (year)")
    week: Optional[int] = Field(None, description="Week number")
    team: Optional[str] = Field(None, description="Team abbreviation")
    limit: int = Field(default=100, description="Max results")
    offset: int = Field(default=0, description="Result offset")


class PlayFilterSchema(BaseModel):
    season: Optional[int] = None
    week: Optional[int] = None
    team: Optional[str] = None
    play_type: Optional[str] = None
    limit: int = Field(default=100)
    offset: int = Field(default=0)

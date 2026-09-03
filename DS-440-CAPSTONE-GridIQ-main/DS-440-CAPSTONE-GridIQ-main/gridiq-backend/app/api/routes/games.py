from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import uuid

from app.api.deps import get_db, get_current_user
from app.models.game import Game, Play
from app.nflverse_schedules import allowed_nflverse_seasons
from app.schemas.game import GameSchema, GameDetailSchema, PlaySchema, GameFilterSchema, PlayFilterSchema

router = APIRouter()

_SYNC_SEASON_MSG = (
    "Only seasons listed in NFLVERSE_SEASONS (gridiq-backend/.env) can be synced."
)


@router.get("/games", response_model=list[GameSchema])
def list_games(
    season: int = Query(None, description="NFL season"),
    week: int = Query(None, description="Week number"),
    team: str = Query(None, description="Team abbreviation"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get games with optional filtering."""
    query = db.query(Game)
    
    if season:
        query = query.filter(Game.season == season)
    if week:
        query = query.filter(Game.week == week)
    if team:
        query = query.filter((Game.home_team == team) | (Game.away_team == team))
    
    games = query.order_by(Game.game_date.desc()).offset(offset).limit(limit).all()
    return games


@router.get("/games/{game_id}", response_model=GameDetailSchema)
def get_game(
    game_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific game with all plays."""
    game = db.query(Game).filter(Game.id == game_id).first()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return game


@router.get("/plays", response_model=list[PlaySchema])
def list_plays(
    season: int = Query(None, description="NFL season"),
    week: int = Query(None, description="Week number"),
    team: str = Query(None, description="Team abbreviation"),
    play_type: str = Query(None, description="Type of play (pass, rush, etc)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get plays with optional filtering."""
    query = db.query(Play)
    
    if season:
        query = query.filter(Play.id.contains(f"_{season}_"))
    if week:
        query = query.filter(Play.id.contains(f"_W{week}_"))
    if team:
        query = query.filter((Play.posteam == team) | (Play.defteam == team))
    if play_type:
        query = query.filter(Play.play_type == play_type)
    
    plays = query.order_by(Play.created_at.desc()).offset(offset).limit(limit).all()
    return plays


@router.get("/plays/{play_id}", response_model=PlaySchema)
def get_play(
    play_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific play."""
    play = db.query(Play).filter(Play.id == play_id).first()
    
    if not play:
        raise HTTPException(status_code=404, detail="Play not found")
    
    return play


@router.get("/plays/team/{team}/stats")
def get_team_stats(
    team: str,
    season: int = Query(None),
    db: Session = Depends(get_db),
):
    """Get offensive and defensive statistics for a team."""
    query = db.query(Play).filter((Play.posteam == team) | (Play.defteam == team))
    
    if season:
        query = query.filter(Play.id.contains(f"_{season}_"))
    
    plays = query.all()
    
    if not plays:
        raise HTTPException(status_code=404, detail="No plays found for team")
    
    # Calculate stats
    offensive_epa = 0
    defensive_epa = 0
    offensive_plays = 0
    defensive_plays = 0
    
    for play in plays:
        if play.posteam == team and play.epa is not None:
            offensive_epa += play.epa
            offensive_plays += 1
        if play.defteam == team and play.epa is not None:
            defensive_epa -= play.epa  # Defense wants negative EPA
            defensive_plays += 1
    
    return {
        "team": team,
        "season": season,
        "offensive_epa": offensive_epa / offensive_plays if offensive_plays > 0 else 0,
        "defensive_epa": defensive_epa / defensive_plays if defensive_plays > 0 else 0,
        "total_plays": len(plays),
    }


@router.post("/sync/games")
def sync_games(
    season: int = Query(..., description="Season to sync"),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync games from nflverse for a season."""
    allowed = allowed_nflverse_seasons()
    if season not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Season {season} is not enabled for nflverse sync. "
                f"Allowed: {sorted(allowed)}. {_SYNC_SEASON_MSG}"
            ),
        )

    try:
        from app.nflverse_schedules import get_schedules_dataframe

        games_data = get_schedules_dataframe()
        games_data = games_data.loc[games_data["season"] == season]
        
        synced_count = 0
        for _, row in games_data.iterrows():
            # Check if game already exists
            existing = db.query(Game).filter(Game.game_id == row['game_id']).first()
            if existing:
                continue
            
            game = Game(
                id=f"game_{uuid.uuid4().hex}",
                game_id=row['game_id'],
                season=season,
                week=row['week'],
                home_team=row['home_team'],
                away_team=row['away_team'],
                home_score=row.get('home_score'),
                away_score=row.get('away_score'),
                game_date=row['gameday'],
                stadium=row.get('stadium'),
            )
            db.add(game)
            synced_count += 1
        
        db.commit()
        return {"synced": synced_count, "season": season}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")


@router.post("/sync/plays")
def sync_plays(
    season: int = Query(..., description="Season to sync"),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync plays from nflverse for a season."""
    allowed = allowed_nflverse_seasons()
    if season not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Season {season} is not enabled for nflverse sync. "
                f"Allowed: {sorted(allowed)}. {_SYNC_SEASON_MSG}"
            ),
        )

    try:
        import nfl_data_py as nfl

        # Fetch plays from nflverse
        plays_data = nfl.import_pbp_data([season])
        
        synced_count = 0
        for _, row in plays_data.iterrows():
            # Check if play already exists
            existing = db.query(Play).filter(Play.play_id == row.get('play_id')).first()
            if existing:
                continue
            
            play = Play(
                id=f"play_{uuid.uuid4().hex}",
                game_id=row.get('game_id', ''),
                play_id=row.get('play_id', f"play_{uuid.uuid4().hex}"),
                quarter=row.get('qtr', 1),
                minute=row.get('minute'),
                second=row.get('second'),
                posteam=row.get('posteam'),
                defteam=row.get('defteam'),
                play_description=row.get('desc'),
                play_type=row.get('play_type'),
                yards_gained=row.get('yards_gained'),
                yards_to_go=row.get('ydstogo'),
                down=row.get('down'),
                epa=row.get('epa'),
                wpa=row.get('wpa'),
                air_yards=row.get('air_yards'),
                yards_after_catch=row.get('yards_after_catch'),
                touchdown=row.get('touchdown', False),
                interception=row.get('interception', False),
                fumble=row.get('fumble', False),
            )
            db.add(play)
            synced_count += 1
        
        db.commit()
        return {"synced": synced_count, "season": season}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")

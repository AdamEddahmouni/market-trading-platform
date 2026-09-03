from fastapi import FastAPI
from app.api.routes import health, auth, users, chat, games, cache, nflverse_dashboard
from app.core.db import engine, Base
from app.core.config import settings
import app.models  # register models for metadata

app = FastAPI(title="GridIQ Backend", version="0.1.0")


@app.on_event("startup")
def create_db_tables() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(nflverse_dashboard.router, prefix="/api/games", tags=["nflverse"])
app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(cache.router, prefix="/api/cache", tags=["cache"])


from fastapi.middleware.cors import CORSMiddleware

# Accept frontend requests in local development on common host/ports.
# Update / lock down origins for production deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
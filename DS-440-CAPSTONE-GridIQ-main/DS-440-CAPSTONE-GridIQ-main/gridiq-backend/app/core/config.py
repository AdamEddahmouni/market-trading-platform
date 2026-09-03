from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path to gridiq-backend/.env (always this folder, never cwd).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_FILE = _BACKEND_ROOT / ".env"

_DEFAULT_SQLITE_URL = "sqlite:///" + str((_BACKEND_ROOT / "gridiq.db").resolve()).replace("\\", "/")


class Settings(BaseSettings):
    ENV: str = "dev"
    DATABASE_URL: str = _DEFAULT_SQLITE_URL

    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 30

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # nflverse: comma-separated NFL years to keep (default 2025 only — less RAM). Example: 2024,2025
    NFLVERSE_SEASONS: str = "2025"

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sqlite_relative_paths_use_backend_root(cls, v: object) -> object:
        """`sqlite:///./gridiq.db` follows the shell cwd and can split data across two .db files; always anchor to this app folder."""
        if not isinstance(v, str) or not v.startswith("sqlite:///./"):
            return v
        rel = v.removeprefix("sqlite:///./").lstrip("/\\")
        if not rel:
            return v
        anchored = (_BACKEND_ROOT / rel).resolve()
        return "sqlite:///" + str(anchored).replace("\\", "/")

    @field_validator("GEMINI_API_KEY", mode="before")
    @classmethod
    def strip_api_keys(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("NFLVERSE_SEASONS", mode="before")
    @classmethod
    def nflverse_seasons_str(cls, v: object) -> object:
        if v is None:
            return "2025"
        if isinstance(v, str):
            t = v.strip()
            return "2025" if t == "" else t
        return str(v).strip() or "2025"

    # Read only os.environ (populated by load_dotenv below). Avoid pydantic merging env_file
    # in a way that drops keys when cwd or precedence differs between machines.
    model_config = SettingsConfigDict(extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load .env into os.environ, then build settings (single cached instance per process)."""
    # utf-8-sig strips UTF-8 BOM from files saved by some Windows editors.
    load_dotenv(_DEFAULT_ENV_FILE, override=True, encoding="utf-8-sig")
    return Settings()


settings = get_settings()

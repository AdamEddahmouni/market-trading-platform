from fastapi import APIRouter

from app.core.config import _DEFAULT_ENV_FILE, get_settings

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/health/ai")
def health_ai():
    """Whether the running server sees API keys (never returns secret values)."""
    s = get_settings()
    return {
        "env_file_path": str(_DEFAULT_ENV_FILE),
        "env_file_exists": _DEFAULT_ENV_FILE.is_file(),
        "gemini_configured": bool(s.GEMINI_API_KEY.strip()),
    }

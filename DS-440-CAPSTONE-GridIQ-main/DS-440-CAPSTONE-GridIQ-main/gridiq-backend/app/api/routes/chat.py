import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.api.deps import get_db, get_current_user
from app.models.conversation import Conversation, Message
from app.models.game import Play
from app.models.user import User
from app.schemas.conversation import (
    ConversationSchema,
    ConversationCreateSchema,
    ConversationUpdateSchema,
    ChatRequestSchema,
    ChatResponseSchema,
    MessageCreateSchema,
)
from app.core.config import Settings, _DEFAULT_ENV_FILE
from app.nflverse_chat_context import build_nflverse_schedule_context
from app.nflverse_chat_pbp import build_optional_play_by_play_section

router = APIRouter()


def _parse_env_file_value(name: str) -> str:
    """Last-resort read from gridiq-backend/.env if os.environ/Settings miss a key (Windows/editor quirks)."""
    if not _DEFAULT_ENV_FILE.is_file():
        return ""
    try:
        text = _DEFAULT_ENV_FILE.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    prefix = f"{name}="
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip('"').strip("'")
    return ""


def _load_chat_settings() -> Settings:
    """Fresh .env load + Settings so each chat message sees current keys (avoids stale process/cache)."""
    load_dotenv(_DEFAULT_ENV_FILE, override=True, encoding="utf-8-sig")
    return Settings()


FOOTBALL_COACH_SYSTEM_PROMPT = """You are an expert AI football coach for GridIQ. You provide:
- Clear explanations of football concepts and strategies
- Analysis of game situations and play-calling decisions
- Data-driven insights based on NFL statistics when context is provided
- Coaching advice tailored to different skill levels
- References to real NFL plays and teams when relevant

When answering questions:
1. Provide accurate football knowledge
2. Reference statistics and data when available in the context below
3. Explain concepts clearly and concisely
4. Ask clarifying questions if needed
5. Consider different skill levels (player, coach, fan)

Use every non-empty section below: **Database plays** (if synced), **nflverse schedule snapshot** (public schedules/scores), and optionally **Attached play-by-play**. Do not invent game results if the snapshot says data is missing.

### Play-by-play
- If **## Attached play-by-play** is present, you may analyze those plays (reference quarter / down & distance when useful).
- If **## Play-by-play** asks you to clarify, do **not** make up plays — ask the listed follow-up questions briefly, then wait for the user."""


def build_football_context(db: Session, team: str = None, season: int = None, week: int = None) -> str:
    """Build football data context for AI from database."""
    context = ""
    
    # Get recent plays for context
    query = db.query(Play)
    if team:
        query = query.filter((Play.posteam == team) | (Play.defteam == team))
    if season:
        query = query.filter(Play.id.contains(f"_{season}_"))
    if week:
        query = query.filter(Play.id.contains(f"_W{week}"))
    
    plays = query.order_by(Play.created_at.desc()).limit(20).all()
    
    if plays:
        context += "\n## Recent NFL Plays for Context:\n"
        for play in plays:
            if play.epa is not None:
                context += f"- {play.play_description} (EPA: {play.epa:.2f}, WPA: {play.wpa})\n"
    
    return context


def _build_user_content(user_message: str, conversation_context: str) -> str:
    parts = []
    if conversation_context.strip():
        parts.append(f"NFL Data Context:\n{conversation_context}")
    parts.append(f"User question:\n{user_message}")
    return "\n\n".join(parts)


def get_ai_response(user_message: str, conversation_context: str, db: Session) -> tuple[str, int, str]:
    """Return (assistant_text, token_count, model_id). Uses Gemini if configured, else setup instructions."""
    user_content = _build_user_content(user_message, conversation_context)
    settings = _load_chat_settings()
    gemini_key = (settings.GEMINI_API_KEY or _parse_env_file_value("GEMINI_API_KEY")).strip()

    if gemini_key:
        try:
            import google.generativeai as genai
            from google.api_core import exceptions as google_exc

            genai.configure(api_key=gemini_key)
            prompt = f"{FOOTBALL_COACH_SYSTEM_PROMPT}\n\n{user_content}"

            # Try GEMINI_MODEL from config/.env first (default: gemini-2.5-flash-lite), then fallbacks if 404/429.
            fallback_models = (
                "gemini-2.5-flash",
                "gemini-flash-latest",
                "gemini-2.0-flash-001",
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
            )
            model_try: list[str] = []
            for m in (settings.GEMINI_MODEL, *fallback_models):
                if m and m.strip():
                    name = m.strip()
                    if name not in model_try:
                        model_try.append(name)

            last_err: Exception | None = None
            response = None
            model_name = model_try[0]
            for mname in model_try:
                try:
                    model = genai.GenerativeModel(mname)
                    response = model.generate_content(prompt)
                    model_name = mname
                    break
                except google_exc.PermissionDenied as e:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Gemini rejected this API key (for example it was revoked or flagged as leaked). "
                            "Create a **new** key at https://aistudio.google.com/apikey , put it in "
                            "**gridiq-backend/.env** as GEMINI_API_KEY, restart the backend, and do not commit or "
                            f"paste the key in chat or public repos. Google said: {e}"
                        ),
                    ) from e
                except (google_exc.ResourceExhausted, google_exc.NotFound) as e:
                    last_err = e
                    continue

            if response is None:
                detail = (
                    "Gemini quota exceeded for the models we tried, or your API project has no access. "
                    f"Last error: {last_err}. Try again later or set GEMINI_MODEL in .env to a model from "
                    "https://ai.google.dev/gemini-api/docs/models."
                )
                if last_err and isinstance(last_err, google_exc.NotFound):
                    detail = (
                        "Gemini model not available for this API/version (tried: "
                        + ", ".join(model_try)
                        + "). Set GEMINI_MODEL in gridiq-backend/.env to a valid ID from "
                        "https://ai.google.dev/gemini-api/docs/models. Last error: "
                        f"{last_err}"
                    )
                raise HTTPException(status_code=503, detail=detail) from last_err

            try:
                assistant_message = (response.text or "").strip()
            except ValueError:
                assistant_message = ""
                if getattr(response, "candidates", None):
                    c0 = response.candidates[0]
                    if c0.content and c0.content.parts:
                        assistant_message = "".join(
                            getattr(p, "text", "") or "" for p in c0.content.parts
                        ).strip()
                if not assistant_message and getattr(response, "prompt_feedback", None):
                    assistant_message = f"(Gemini blocked or empty reply: {response.prompt_feedback})"
            tokens_used = response.usage_metadata.total_token_count if response.usage_metadata else 0
            return assistant_message, tokens_used, model_name
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}") from e

    fallback = (
        "No **GEMINI_API_KEY** is configured (Gemini only—OpenAI is not used). "
        "Add it to **gridiq-backend/.env** and restart the server.\n\n"
        "- Create a key at https://aistudio.google.com/apikey\n"
        "- Optional: **GEMINI_MODEL** (default `gemini-2.5-flash-lite`).\n\n"
        "_If you see older text mentioning OpenAI, that was saved chat history in SQLite—not this server build._"
    )
    return fallback, 0, "none"


@router.post("/conversations", response_model=ConversationSchema)
def create_conversation(
    payload: ConversationCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation."""
    conversation = Conversation(
        id=f"conv_{uuid.uuid4().hex}",
        user_id=current_user.id,
        title=payload.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[ConversationSchema])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all conversations for the user."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationSchema)
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific conversation with all messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@router.put("/conversations/{conversation_id}", response_model=ConversationSchema)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a conversation title."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if payload.title:
        conversation.title = payload.title
    
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    
    return {"detail": "Conversation deleted"}


@router.post("/chat", response_model=ChatResponseSchema)
def chat(
    payload: ChatRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message and get AI coach response."""
    
    # Get or create conversation
    if payload.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == payload.conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
        if not conversation:
            # Client-supplied IDs can collide across users; issue a fresh server ID.
            conversation = Conversation(
                id=f"conv_{uuid.uuid4().hex}",
                user_id=current_user.id,
                title="New Conversation",
            )
            db.add(conversation)
            db.flush()
    else:
        conversation = Conversation(
            id=f"conv_{uuid.uuid4().hex}",
            user_id=current_user.id,
            title="New Conversation",
        )
        db.add(conversation)
        db.flush()
    
    # Save user message
    user_message_obj = Message(
        id=f"msg_{uuid.uuid4().hex}",
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_message_obj)
    db.flush()

    hist = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    transcript = "\n".join(f"{m.role}: {(m.content or '')[:1500]}" for m in hist[-16:])

    # SQLite plays (if any) + nflverse schedule + optional on-demand PBP (same Gemini payload, no API contract change)
    db_ctx = build_football_context(db).strip()
    verse_ctx = build_nflverse_schedule_context(payload.message).strip()
    pbp_ctx = build_optional_play_by_play_section(transcript, payload.message).strip()
    football_context = "\n\n".join(x for x in (db_ctx, verse_ctx, pbp_ctx) if x)
    
    # Get AI response (on Gemini 503/500, persist explanation so the thread updates instead of only an HTTP error panel).
    try:
        assistant_message, tokens_used, model_used = get_ai_response(
            payload.message,
            football_context,
            db,
        )
    except HTTPException as exc:
        detail: str
        if isinstance(exc.detail, str):
            detail = exc.detail
        elif isinstance(exc.detail, list):
            detail = "; ".join(str(item) for item in exc.detail)
        else:
            detail = str(exc.detail)

        detail_lower = detail.lower()
        if "spending cap" in detail_lower or "exceeded its spending" in detail_lower:
            hint = (
                "**Google blocked the request because of a billing / spending limit on this Cloud or AI Studio project**, "
                "not because of GridIQ code. Open Google Cloud Console → Billing for the project tied to your API key, "
                "and raise or remove the monthly budget / spending cap, or fix payment. "
                "Also check APIs & Services and usage in Google AI Studio. "
                "Until billing allows charges again, every model may keep returning 429."
            )
        else:
            hint = (
                "If Google AI Studio shows **404**, the model name may be invalid for your project. "
                "If it shows **429** for quota only (not spending cap), try again later or set **GEMINI_MODEL=gemini-2.5-flash-lite** in "
                "`gridiq-backend/.env`, restart uvicorn, and send again."
            )

        assistant_message = "The AI request did not complete successfully.\n\n" f"{detail}\n\n" f"{hint}"
        tokens_used = 0
        model_used = "error"

    # Save assistant message
    assistant_message_obj = Message(
        id=f"msg_{uuid.uuid4().hex}",
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_message,
        model=model_used,
        tokens_used=tokens_used,
    )
    db.add(assistant_message_obj)
    
    db.commit()
    
    return ChatResponseSchema(
        conversation_id=conversation.id,
        user_message=payload.message,
        assistant_message=assistant_message,
        model=model_used,
        tokens_used=tokens_used,
    )

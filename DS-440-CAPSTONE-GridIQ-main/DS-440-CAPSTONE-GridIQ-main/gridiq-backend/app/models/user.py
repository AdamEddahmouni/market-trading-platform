from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class User(Base):
    __tablename__ = "users"

    # Use string IDs to match frontend Zod schema
    id: Mapped[str] = mapped_column(String(50), primary_key=True)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Coach")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="coach")

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
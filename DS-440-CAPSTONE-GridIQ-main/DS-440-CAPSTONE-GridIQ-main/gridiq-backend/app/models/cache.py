from sqlalchemy import String, DateTime, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class Cache(Base):
    __tablename__ = "cache"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON serialized
    
    # TTL in seconds (0 = no expiration)
    ttl: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

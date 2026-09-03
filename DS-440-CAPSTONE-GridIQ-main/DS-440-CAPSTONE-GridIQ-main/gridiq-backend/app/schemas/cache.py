from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class CacheSchema(BaseModel):
    id: str
    key: str
    value: str  # JSON serialized
    ttl: int
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CacheSetSchema(BaseModel):
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cache value (will be JSON serialized)")
    ttl: int = Field(default=3600, description="Time to live in seconds")


class CacheGetSchema(BaseModel):
    key: str = Field(..., description="Cache key to retrieve")


class CacheResponseSchema(BaseModel):
    key: str
    value: Any
    expires_at: Optional[datetime] = None

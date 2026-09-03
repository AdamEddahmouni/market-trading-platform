import json
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.cache import Cache
from app.schemas.cache import CacheSchema, CacheSetSchema, CacheResponseSchema

router = APIRouter()


@router.post("/cache", response_model=CacheSchema)
def set_cache(
    payload: CacheSetSchema,
    db: Session = Depends(get_db),
):
    """Set a cache entry."""
    # Check if key already exists
    existing = db.query(Cache).filter(Cache.key == payload.key).first()
    
    cache_id = existing.id if existing else f"cache_{uuid.uuid4().hex}"
    
    # Calculate expiration time
    expires_at = datetime.utcnow() + timedelta(seconds=payload.ttl) if payload.ttl > 0 else None
    
    cache_entry = Cache(
        id=cache_id,
        key=payload.key,
        value=json.dumps(payload.value) if not isinstance(payload.value, str) else payload.value,
        ttl=payload.ttl,
        expires_at=expires_at,
    )
    
    if existing:
        db.merge(cache_entry)
    else:
        db.add(cache_entry)
    
    db.commit()
    db.refresh(cache_entry)
    return cache_entry


@router.get("/cache/{key}", response_model=CacheResponseSchema)
def get_cache(
    key: str,
    db: Session = Depends(get_db),
):
    """Get a cache entry by key."""
    cache_entry = db.query(Cache).filter(Cache.key == key).first()
    
    if not cache_entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    
    # Check if expired
    if cache_entry.expires_at and cache_entry.expires_at < datetime.utcnow():
        db.delete(cache_entry)
        db.commit()
        raise HTTPException(status_code=404, detail="Cache entry expired")
    
    # Parse value back to original type
    try:
        value = json.loads(cache_entry.value)
    except json.JSONDecodeError:
        value = cache_entry.value
    
    return CacheResponseSchema(
        key=cache_entry.key,
        value=value,
        expires_at=cache_entry.expires_at,
    )


@router.delete("/cache/{key}")
def delete_cache(
    key: str,
    db: Session = Depends(get_db),
):
    """Delete a cache entry."""
    cache_entry = db.query(Cache).filter(Cache.key == key).first()
    
    if not cache_entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    
    db.delete(cache_entry)
    db.commit()
    
    return {"detail": "Cache entry deleted"}


@router.delete("/cache")
def clear_cache(
    db: Session = Depends(get_db),
):
    """Clear all cache entries."""
    db.query(Cache).delete()
    db.commit()
    
    return {"detail": "All cache entries cleared"}


@router.post("/cache/cleanup")
def cleanup_expired_cache(
    db: Session = Depends(get_db),
):
    """Remove all expired cache entries."""
    now = datetime.utcnow()
    deleted = db.query(Cache).filter(Cache.expires_at < now).delete()
    db.commit()
    
    return {"deleted": deleted}

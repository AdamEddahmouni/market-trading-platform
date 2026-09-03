from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.schemas.user import UserOut
from app.models.user import User

router = APIRouter()

@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return UserOut(id=current.id, email=current.email, displayName=current.display_name, role=current.role)

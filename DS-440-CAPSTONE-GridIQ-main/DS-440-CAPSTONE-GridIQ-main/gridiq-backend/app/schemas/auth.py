from pydantic import BaseModel, EmailStr
from app.schemas.user import UserOut

class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class AuthOut(BaseModel):
    token: str
    user: UserOut
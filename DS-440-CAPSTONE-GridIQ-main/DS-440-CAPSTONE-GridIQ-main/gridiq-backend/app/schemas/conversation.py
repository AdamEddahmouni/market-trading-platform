from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class MessageSchema(BaseModel):
    id: str
    role: str  # "user" or "assistant"
    content: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSchema(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageSchema] = []

    class Config:
        from_attributes = True


class ConversationCreateSchema(BaseModel):
    title: Optional[str] = Field(default="New Conversation", description="Title for the conversation")


class ConversationUpdateSchema(BaseModel):
    title: Optional[str] = None


class MessageCreateSchema(BaseModel):
    content: str = Field(..., description="The message content")


class ChatRequestSchema(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., description="User's message")


class ChatResponseSchema(BaseModel):
    conversation_id: str
    user_message: str
    assistant_message: str
    model: str = "gemini-2.5-flash-lite"
    tokens_used: int

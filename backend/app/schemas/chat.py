"""Request/response shapes for chat."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ChatDetail(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    messages: list[MessageResponse]
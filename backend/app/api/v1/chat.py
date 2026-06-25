"""
Chat endpoints. All require login via get_current_user.
Routes (under prefix /api/v1/chats):
  POST   ""                 create a chat
  GET    ""                 list my chats
  GET    /{chat_id}         get one chat with its messages
  POST   /{chat_id}/messages  send a message, get an AI reply
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatCreate, ChatDetail, ChatSummary, MessageCreate, MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("", response_model=ChatSummary, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await ChatService(db).create_chat(current_user.id, body.title)
    return ChatSummary.model_validate(chat)


@router.get("", response_model=list[ChatSummary])
async def list_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chats = await ChatService(db).list_chats(current_user.id)
    return [ChatSummary.model_validate(c) for c in chats]


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat, messages = await ChatService(db).get_chat_with_messages(
        current_user.id, chat_id
    )
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.post(
    "/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    chat_id: uuid.UUID,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assistant = await ChatService(db).send_message(
        current_user.id, chat_id, body.content
    )
    return MessageResponse.model_validate(assistant)
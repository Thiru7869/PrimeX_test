"""
Chat business logic. Saves messages, builds conversation history, and calls
the AI Gateway. Raises HTTPException on problems (same pattern as AuthService).
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.ai_gateway import AIGateway
from app.models.chat import Chat
from app.models.message import Message
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.chats = ChatRepository(db)
        self.messages = MessageRepository(db)
        self.gateway = AIGateway()

    async def create_chat(self, user_id: uuid.UUID, title: str | None) -> Chat:
        chat = await self.chats.create(user_id, title or "New chat")
        await self.db.commit()
        return chat

    async def list_chats(self, user_id: uuid.UUID) -> list[Chat]:
        return await self.chats.list_for_user(user_id)

    async def _get_owned_chat(self, user_id: uuid.UUID, chat_id: uuid.UUID) -> Chat:
        chat = await self.chats.get_by_id(chat_id)
        if not chat or chat.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found.")
        return chat

    async def get_chat_with_messages(
        self, user_id: uuid.UUID, chat_id: uuid.UUID
    ) -> tuple[Chat, list[Message]]:
        chat = await self._get_owned_chat(user_id, chat_id)
        messages = await self.messages.list_for_chat(chat_id)
        return chat, messages

    async def send_message(
        self, user_id: uuid.UUID, chat_id: uuid.UUID, content: str
    ) -> Message:
        chat = await self._get_owned_chat(user_id, chat_id)

        # 1. Save the user's message.
        await self.messages.create(chat_id=chat.id, role="user", content=content)

        # 2. Build the conversation history (including the new message).
        history_rows = await self.messages.list_for_chat(chat.id)
        history = [{"role": m.role, "content": m.content} for m in history_rows]

        # 3. Ask the AI via the Gateway.
        try:
            result = await self.gateway.chat(history, user_id=user_id, db=self.db)
        except Exception as exc:
            # The turn failed; throw it all away so nothing half-saved remains.
            await self.db.rollback()
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"AI provider error: {exc}"
            )

        # 4. Save the assistant's reply.
        assistant = await self.messages.create(
            chat_id=chat.id,
            role="assistant",
            content=result.text,
            provider=result.provider,
            model=result.model,
            token_count=result.tokens,
        )
        await self.db.commit()
        await self.db.refresh(assistant)
        return assistant
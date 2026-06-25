"""Database access for the chats table."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str) -> Chat:
        chat = Chat(user_id=user_id, title=title)
        self.db.add(chat)
        await self.db.flush()
        await self.db.refresh(chat)
        return chat

    async def get_by_id(self, chat_id: uuid.UUID) -> Chat | None:
        result = await self.db.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Chat]:
        result = await self.db.execute(
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc())
        )
        return list(result.scalars().all())
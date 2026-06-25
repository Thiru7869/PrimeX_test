"""Database access for the messages table."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        chat_id: uuid.UUID,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        token_count: int | None = None,
    ) -> Message:
        msg = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            token_count=token_count,
        )
        self.db.add(msg)
        await self.db.flush()
        await self.db.refresh(msg)
        return msg

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
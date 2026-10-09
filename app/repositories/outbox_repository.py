from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox, OutboxStatus


class OutboxRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, outbox: Outbox) -> Outbox:
        self.session.add(outbox)
        await self.session.flush()
        return outbox

    async def get_pending_events(self) -> list[Outbox]:
        result = await self.session.execute(
            select(Outbox)
            .where(Outbox.status == OutboxStatus.PENDING)
            .order_by(Outbox.created_at)
        )

        return list(result.scalars().all())

    async def update(self, outbox: Outbox):
        await self.session.flush()
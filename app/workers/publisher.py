import asyncio
from datetime import datetime, UTC

from app.db.database import AsyncSessionLocal
from app.models.outbox import OutboxStatus
from app.rabbit.broker import broker
from app.rabbit.queues import PAYMENTS_QUEUE
from app.repositories.outbox_repository import OutboxRepository

POLL_INTERVAL_SECONDS = 2


async def publish_outbox_events():

    async with AsyncSessionLocal() as session:

        repository = OutboxRepository(session)

        events = await repository.get_pending_events()

        for event in events:

            try:
                await broker.publish(
                    message=event.payload,
                    queue=PAYMENTS_QUEUE,
                )

                event.status = OutboxStatus.PUBLISHED
                event.published_at = datetime.now(UTC)

                await repository.update(event)

            except Exception:
                event.attempts += 1

                if event.attempts >= 3:
                    event.status = OutboxStatus.FAILED

                await repository.update(event)

        await session.commit()


async def main():
    await broker.start()

    print("Publisher started...")

    try:
        while True:
            await publish_outbox_events()
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import random
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.payment import Payment, PaymentStatus
from app.rabbit.broker import broker
from app.rabbit.queues import PAYMENTS_DLQ, PAYMENTS_QUEUE
from app.workers.webhook import send_webhook


@broker.subscriber(PAYMENTS_QUEUE)
async def process_payment(message: dict):
    attempts = message.get("attempts", 0)

    try:
        payment_id = UUID(message["payment_id"])

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )

            payment = result.scalar_one_or_none()

            if payment is None:
                return

            if payment.status != PaymentStatus.PENDING:
                return

            await asyncio.sleep(random.randint(2, 5))

            success = random.random() <= 0.9

            payment.status = (
                PaymentStatus.SUCCEEDED
                if success
                else PaymentStatus.FAILED
            )
            payment.processed_at = datetime.now(UTC)

            await session.commit()

            await send_webhook(payment)

    except Exception as exc:
        attempts += 1

        if attempts >= 3:
            await broker.publish(
                message={
                    **message,
                    "attempts": attempts,
                    "error": str(exc),
                },
                queue=PAYMENTS_DLQ,
            )
            return

        await asyncio.sleep(2 ** attempts)

        await broker.publish(
            message={
                **message,
                "attempts": attempts,
            },
            queue=PAYMENTS_QUEUE,
        )
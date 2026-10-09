from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox, OutboxStatus
from app.models.payment import Payment, PaymentStatus
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import (
    PaymentAcceptedResponse,
    PaymentCreate,
)


class PaymentService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_repository = PaymentRepository(session)
        self.outbox_repository = OutboxRepository(session)

    async def create_payment(
        self,
        payment: PaymentCreate,
        idempotency_key: str,
    ) -> PaymentAcceptedResponse:

        # Check idempotency
        existing_payment = await self.payment_repository.get_by_idempotency_key(
            idempotency_key
        )

        if existing_payment:
            return PaymentAcceptedResponse(
                payment_id=existing_payment.id,
                status=existing_payment.status,
                created_at=existing_payment.created_at,
            )

        # Create payment
        new_payment = Payment(
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.metadata,
            webhook_url=str(payment.webhook_url),
            idempotency_key=idempotency_key,
            status=PaymentStatus.PENDING,
        )

        try:
            # Save payment
            await self.payment_repository.create(new_payment)

            # Create outbox event
            outbox_event = Outbox(
                event_type="payments.new",
                payload={
                    "payment_id": str(new_payment.id),
                    "amount": str(new_payment.amount),
                    "currency": new_payment.currency,
                    "description": new_payment.description,
                    "webhook_url": new_payment.webhook_url,
                },
                status=OutboxStatus.PENDING,
            )

            # Save outbox event
            await self.outbox_repository.create(outbox_event)

            # Commit transaction
            await self.session.commit()

            # Refresh objects
            await self.session.refresh(new_payment)
            await self.session.refresh(outbox_event)

            return PaymentAcceptedResponse(
                payment_id=new_payment.id,
                status=new_payment.status,
                created_at=new_payment.created_at,
            )

        except Exception:
            await self.session.rollback()
            raise

    async def get_payment(
        self,
        payment_id: UUID,
    ) -> Payment | None:
        return await self.payment_repository.get_by_id(payment_id)
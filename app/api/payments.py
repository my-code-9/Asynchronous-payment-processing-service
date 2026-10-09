from uuid import UUID

from app.core.sercurity import verify_api_key
from fastapi import Security

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.payment import (
    PaymentAcceptedResponse,
    PaymentCreate,
    PaymentResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(
    prefix="/api/v1/payments",
    tags=["Payments"],
)


@router.post(
    "",
    response_model=PaymentAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment(
    payment: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Security(verify_api_key),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        description="Unique idempotency key",
    ),
):
    service = PaymentService(db)

    return await service.create_payment(
        payment=payment,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Security(verify_api_key),
):
    service = PaymentService(db)

    payment = await service.get_payment(payment_id)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return PaymentResponse(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata_,
        status=payment.status,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
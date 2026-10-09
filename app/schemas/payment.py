from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.payment import PaymentStatus
from app.utils.url_safety import UnsafeWebhookURLError, ensure_safe_webhook_url


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., pattern="^(RUB|USD|EUR)$")
    description: str | None = None
    metadata: dict[str, Any] = {}
    webhook_url: HttpUrl

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: HttpUrl) -> HttpUrl:
        try:
            ensure_safe_webhook_url(str(value))
        except UnsafeWebhookURLError as exc:
            raise ValueError(str(exc)) from exc

        return value


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: str
    description: str | None
    metadata: dict[str, Any]
    status: PaymentStatus
    webhook_url: HttpUrl
    created_at: datetime
    processed_at: datetime | None


class PaymentAcceptedResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime
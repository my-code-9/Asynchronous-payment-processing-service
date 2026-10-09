import asyncio

import httpx

from app.models.payment import Payment
from app.utils.url_safety import ensure_safe_webhook_url


class WebhookDeliveryError(Exception):
    """Raised when webhook delivery fails after all retries."""


async def send_webhook(payment: Payment) -> None:
    await asyncio.to_thread(ensure_safe_webhook_url, payment.webhook_url)

    payload = {
        "payment_id": str(payment.id),
        "status": payment.status.value,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "description": payment.description,
    }

    retry_delays = [1, 2, 4]

    async with httpx.AsyncClient(timeout=10) as client:

        for attempt, delay in enumerate(retry_delays, start=1):

            try:
                response = await client.post(
                    payment.webhook_url,
                    json=payload,
                )

                response.raise_for_status()

                return

            except Exception:

                if attempt == len(retry_delays):
                    raise WebhookDeliveryError(
                        "Webhook delivery failed after 3 attempts."
                    )

                await asyncio.sleep(delay)
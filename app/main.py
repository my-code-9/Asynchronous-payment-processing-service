from fastapi import FastAPI

from app.api.payments import router as payment_router

from app.core.config import settings

app = FastAPI(
    title="Payment Service",
    version="1.0.0",
)

app.include_router(payment_router)


@app.get("/")
async def root():
    return {
        "message": "Payment Service"
    }
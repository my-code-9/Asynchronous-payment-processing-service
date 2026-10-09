import asyncio

from app.rabbit.broker import broker

# Import subscribers
import app.workers.consumer


async def main():
    await broker.start()

    print("Worker started...")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
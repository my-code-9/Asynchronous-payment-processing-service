# Payment Service

An asynchronous payment processing service built with FastAPI, PostgreSQL, RabbitMQ (FastStream), SQLAlchemy Async, and the Transactional Outbox Pattern.

The service accepts payment requests, emulates processing through an external payment gateway, and notifies the caller of the result via webhook.

---

## Requirements Coverage

This project was built against the following assignment spec. Status reflects the current state of the code.

| Requirement | Status | Notes |
|---|---|---|
| `POST /api/v1/payments` — create payment, `Idempotency-Key` header required, returns `202` + `payment_id`/`status`/`created_at` | Done | [api/payments.py](app/api/payments.py) |
| `GET /api/v1/payments/{payment_id}` — full payment details | Done | [api/payments.py](app/api/payments.py) |
| Payment entity: id, amount (decimal), currency (RUB/USD/EUR), description, metadata (JSON), status, idempotency key, webhook URL, created/processed timestamps | Done | [models/payment.py](app/models/payment.py) |
| Event `payments.new` published on payment creation | Done | via Outbox → Publisher, not published directly from the request handler |
| Single consumer: reads message, emulates processing (2–5s, 90% success / 10% failure), updates status, sends webhook, retries on failure | Done | [workers/consumer.py](app/workers/consumer.py) |
| Outbox pattern for guaranteed event publishing | Done | [models/outbox.py](app/models/outbox.py), [workers/publisher.py](app/workers/publisher.py) |
| Idempotency key protection | Done | unique DB constraint + lookup in [services/payment_service.py](app/services/payment_service.py) |
| Dead Letter Queue after 3 failed attempts | Done | [workers/consumer.py](app/workers/consumer.py), queue `payments.dlq` |
| Static `X-API-Key` header auth on payment endpoints | Done | [core/sercurity.py](app/core/sercurity.py) |
| FastAPI + Pydantic v2, SQLAlchemy 2.0 async, PostgreSQL, RabbitMQ (FastStream), Alembic, Docker Compose | Done | see Technology Stack below |
| Retry: 3 attempts with exponential backoff | Done | both outbox publishing and message processing back off as `2 ** attempts` |
| Docker Compose: postgres, rabbitmq, api, consumer | Done, plus one addition | a dedicated `publisher` service was added — without it, outbox events are written to the database but never actually make it to RabbitMQ, which breaks the guaranteed-delivery requirement |

Known gap: a `PAYMENTS_EXCHANGE` constant is declared in [rabbit/queues.py](app/rabbit/queues.py) but unused — messages are published straight to the named queue via RabbitMQ's default exchange rather than through a dedicated exchange/binding. Functionally this still delivers messages correctly, but it doesn't demonstrate explicit exchange routing.

---

## Features

- RESTful API built with FastAPI
- Async SQLAlchemy 2.0
- PostgreSQL database
- RabbitMQ message broker (FastStream)
- Alembic database migrations
- Transactional Outbox Pattern
- Idempotent payment creation
- Background publisher worker (outbox → RabbitMQ)
- Background consumer worker (payment processing + webhook delivery)
- Webhook delivery with retries and SSRF protection
- Dead Letter Queue for permanently failed messages
- Static API key authentication
- Docker and Docker Compose support
- OpenAPI / Swagger documentation

---

## Technology Stack

| Technology | Version |
|------------|---------|
| Python | 3.13 |
| FastAPI | Latest |
| SQLAlchemy | 2.x |
| PostgreSQL | 16 |
| asyncpg | Latest |
| RabbitMQ | 3.x |
| FastStream | Latest |
| Alembic | Latest |
| Pydantic | v2 |
| Docker | Latest |

---

## Project Structure

```text
asynchronous-payment-processing-service/
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── README
│   └── script.py.mako
│
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── payments.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── sercurity.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── payment.py
│   │   └── outbox.py
│   │
│   ├── rabbit/
│   │   ├── __init__.py
│   │   ├── broker.py
│   │   └── queues.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── payment_repository.py
│   │   └── outbox_repository.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── payment.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── payment_service.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── url_safety.py
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── consumer.py
│   │   ├── publisher.py
│   │   ├── webhook.py
│   │   └── worker.py
│   │
│   ├── __init__.py
│   └── main.py
│
├── .env
├── .env.example
├── .dockerignore
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── README.md
└── requirements.txt
```

---

## Architecture

```
                    Client
                       │
                       ▼
              POST /api/v1/payments
                       │
                       ▼
                FastAPI Router
                       │
                       ▼
               Payment Service
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
 Payment Repository        Outbox Repository
          │                         │
          └────────────┬────────────┘
                       ▼
                  PostgreSQL
             ┌───────────────────┐
             │ payments           │
             │ outbox             │
             └───────────────────┘
                       │
                       ▼
             Publisher Worker
                       │
                       ▼
                  RabbitMQ
               (payments.new)
                       │
                       ▼
              Consumer Worker
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      Webhook Delivery     payments.dlq
    (after 3 retries)   (after 3 failed attempts)
```

---

## Transactional Outbox Pattern

The application stores both the payment and its corresponding event inside the same database transaction.

```
BEGIN TRANSACTION

INSERT INTO payments

INSERT INTO outbox

COMMIT
```

A background publisher worker polls the `outbox` table and publishes pending events to RabbitMQ, marking them `published` on success or incrementing `attempts` (→ `failed` after 3) on error.

This guarantees that no event is lost even if RabbitMQ is temporarily unavailable at the moment the payment is created.

---

## Reliability & Security

- **Idempotency** — `Idempotency-Key` is a unique, indexed column; a repeated key returns the existing payment instead of creating a duplicate.
- **Retries with backoff** — both outbox publishing and payment processing retry up to 3 times with exponential backoff (`2 ** attempts` seconds) before giving up.
- **Dead Letter Queue** — messages that fail 3 processing attempts are routed to `payments.dlq` instead of being dropped or retried forever.
- **Webhook delivery** — up to 3 attempts with fixed backoff (1s / 2s / 4s) via `httpx`.
- **SSRF protection** — `webhook_url` is validated both at request time and again immediately before delivery; URLs resolving to loopback, private, link-local, reserved, or multicast addresses (e.g. `127.0.0.1`, `192.168.x.x`, the `169.254.169.254` cloud metadata endpoint) are rejected. See [utils/url_safety.py](app/utils/url_safety.py).
- **Authentication** — every payment endpoint requires a static `X-API-Key` header, checked with a constant-time comparison (`secrets.compare_digest`).

---

## Installation

### Clone the repository

```bash
git clone git@github.com:my-code-9/Asynchronous-payment-processing-service.git

cd Asynchronous-payment-processing-service
```

---

### Create a virtual environment

Windows

```bash
python -m venv .venv

.venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv .venv

source .venv/bin/activate
```

---

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file (see `.env.example`).

```env
DATABASE_URL=postgresql+asyncpg://payments:payments@localhost:5433/payments

RABBIT_URL=amqp://guest:guest@localhost:5672/

API_KEY=secret-key

DB_ECHO=false
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy connection string for PostgreSQL |
| `RABBIT_URL` | AMQP connection string for RabbitMQ |
| `API_KEY` | Static key required in the `X-API-Key` header |
| `DB_ECHO` | Logs every SQL statement when `true`; keep `false` outside local debugging |

---

## Start Infrastructure

```bash
docker compose up -d --build
```

This starts four services: `postgres`, `rabbitmq`, `api`, `worker` (consumer), and `publisher`.

Verify containers

```bash
docker ps
```

Expected

```
payment-postgres
payment-rabbitmq
payment-api
payment-worker
payment-publisher
```

---

## Database Migration

Generate migration

```bash
alembic revision --autogenerate -m "initial"
```

Apply migration

```bash
alembic upgrade head
```

Verify

```bash
alembic current
```

---

## Run the API

```bash
uvicorn app.main:app --reload
```

Open Swagger UI

```
http://127.0.0.1:8000/docs
```

---

## API Examples

### Create Payment

**POST** `/api/v1/payments`

Headers

```
Idempotency-Key: payment-001
X-API-Key: secret-key
```

Request

```json
{
    "amount": 100.50,
    "currency": "USD",
    "description": "Order #4821",
    "metadata": {"order_id": "4821"},
    "webhook_url": "https://webhook.site/123456"
}
```

Response — `202 Accepted`

```json
{
    "payment_id": "edfffe65-b59d-407d-a0a7-8a518278447f",
    "status": "pending",
    "created_at": "2026-06-30T09:36:08Z"
}
```

### Get Payment

**GET** `/api/v1/payments/{payment_id}`

Headers

```
X-API-Key: secret-key
```

Response — `200 OK`

```json
{
    "id": "edfffe65-b59d-407d-a0a7-8a518278447f",
    "amount": 100.50,
    "currency": "USD",
    "description": "Order #4821",
    "metadata": {"order_id": "4821"},
    "status": "succeeded",
    "webhook_url": "https://webhook.site/123456",
    "created_at": "2026-06-30T09:36:08Z",
    "processed_at": "2026-06-30T09:36:12Z"
}
```

---

## Verify Database

Open PostgreSQL

```bash
docker exec -it payment-postgres psql -U payments -d payments
```

Check payments

```sql
SELECT * FROM payments;
```

Example

| id | amount | currency | status |
|----|---------|----------|--------|
| edfffe65... | 100.50 | USD | succeeded |

Check outbox

```sql
SELECT * FROM outbox;
```

Example

| event_type | status | attempts |
|------------|---------|----------|
| payments.new | published | 0 |

---

## RabbitMQ

Management Console

```
http://localhost:15672
```

Default credentials

```
Username: guest
Password: guest
```

Queues:

- `payments.new` — events awaiting processing by the consumer
- `payments.dlq` — events that failed processing 3 times

---

## Development Commands

Start Docker

```bash
docker compose up -d
```

Stop Docker

```bash
docker compose down
```

Create migration

```bash
alembic revision --autogenerate -m "message"
```

Run migrations

```bash
alembic upgrade head
```

Rollback

```bash
alembic downgrade -1
```

Run API

```bash
uvicorn app.main:app --reload
```

Run Publisher Worker

```bash
python -m app.workers.publisher
```

Run Consumer Worker

```bash
python -m app.workers.consumer
```

Run Main Worker (imports the consumer, used by Docker Compose)

```bash
python -m app.workers.worker
```

---

## Current Status

- [x] Docker Compose (postgres, rabbitmq, api, worker, publisher)
- [x] PostgreSQL
- [x] RabbitMQ (FastStream)
- [x] FastAPI
- [x] SQLAlchemy Async
- [x] Alembic
- [x] Transactional Outbox Pattern
- [x] Idempotent Payment API
- [x] Payment Repository
- [x] Outbox Repository
- [x] Publisher Worker
- [x] Consumer Worker
- [x] Webhook delivery with retries
- [x] Dead Letter Queue
- [x] Swagger Documentation
- [x] API Key Authentication (constant-time comparison)
- [x] SSRF protection on webhook URLs

---

## Future Improvements

- Dedicated RabbitMQ exchange with explicit bindings (currently publishes via the default exchange)
- Prometheus metrics
- OpenTelemetry tracing
- Structured logging
- Unit tests
- Integration tests
- GitHub Actions CI/CD
- Kubernetes deployment
- Helm charts

---

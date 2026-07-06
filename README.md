# ClaimMesh

A distributed, event-driven insurance claims processing platform. Built as a small mesh of independently deployable services rather than a monolith: an async FastAPI CRUD API, a Celery worker for heavy/background processing, a decoupled notification consumer, Redis for caching, RabbitMQ as the broker, PostgreSQL for persistence, and KrakenD as the API gateway.

## Architecture

| Service                           | Responsibility                                                                        |
| --------------------------------- | ------------------------------------------------------------------------------------- |
| `backend`                         | HTTP API, request validation, reads (cached via Redis), enqueues heavy work to Celery |
| `worker`                          | CSV cleaning, validation, business rules, bulk insert, fraud-flag recomputation       |
| `notification_service`            | Plain RabbitMQ consumer reacting to domain events (upload completed, fraud flagged)   |
| `gateway`                         | KrakenD — single entrypoint (`localhost:8080`)                                        |
| `postgres` / `redis` / `rabbitmq` | System of record / cache / message broker                                             |

The worker and notification_service are never required for the API to boot — if RabbitMQ is down, `/upload` fails cleanly with a `503` instead of taking the whole system down.

## Prerequisites

- Docker & Docker Compose
- [`uv`](https://docs.astral.sh/uv/) (only needed if running a service outside Docker)
- Make

## Setup

1. **Clone and configure environment**

   ```bash
   git clone github.com/Now-Tiger/claimmesh && cd claimmesh
   cp .env.example .env
   ```

   Edit `.env` and set a real(**anything**) `API_KEY` (used by all endpoints except `/health`).

2. **Start infrastructure and services**

   ```bash
   make up
   ```

   This builds and starts `postgres`, `redis`, `rabbitmq`, `backend`, `worker`, `notification-service`, and `gateway`.

3. **Run database migrations**

   ```bash
   make migrate
   ```

4. **Verify health**

   ```bash
   curl http://localhost:8000/health
   ```

   Expected:

   ```json
   { "status": "healthy", "database": "connected", "uptime": "0h 1m" }
   ```

## Usage

All endpoints except `/health` require an `X-API-Key` header matching `API_KEY` from `.env`.

```bash
# Ingest data (synchronous — returns counts directly)
curl -H "X-API-Key: $API_KEY" \
  -F customers=@customer.csv -F policies=@policy.csv -F claims=@claims.csv \
  "http://localhost:8000/upload?sync=true"

# Claim details
curl -H "X-API-Key: $API_KEY" http://localhost:8000/claims/CL001

# Search claims
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/claims?state=CA&sort_by=payout_amount"

# Top customers by payout
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/customers/top?n=10"

# State-level report
curl -H "X-API-Key: $API_KEY" http://localhost:8000/reports/state
```

Interactive API docs (Swagger): **<http://localhost:8000/docs>**

Route everything through the gateway instead by hitting `http://localhost:8080/api/v1/...`.

## Logs & Observability

```bash
make logs                                   # all services, tailed
docker compose logs -f backend              # structured request logs (loguru, JSON)
docker compose logs -f worker                # CSV ingestion / fraud-flag recompute logs
docker compose logs -f notification-service # domain event notifications
```

Backend logs also persist to `backend/logs/claimmesh-backend.log` (rotated at 10 MB, retained 7 days).

Prometheus metrics are exposed at `http://localhost:8000/metrics` and scraped by the `prometheus` container (`http://localhost:9090`); RabbitMQ's management UI is at `http://localhost:15672` (guest/guest).

## Load Testing

```bash
make test-load
```

Runs `backend/tests/load_tester.py` against the live stack and prints p50/p95 latency for `/claims`, `/customers/top`, and `/reports/state`.

## Shutting Down

```bash
make down
```

## Design Notes & Known Trade-offs

- **Payout formula** (deductible → cap → minor discount → floor) is documented verbatim in `backend/services/payout.py`; the assignment did not specify ordering explicitly, so this is a stated assumption, not a silent guess.
- **Fraud flagging** is a stored column on `customers`, recomputed asynchronously by the worker after each upload batch — not calculated on every read.
- **Caching** is TTL-only (60s), not explicitly invalidated on upload, since upload processing time is comparable to the TTL window.
- **Out of scope** (per the assignment's own instructions): KrakenD rate limiting, Pytest/Black, full Prometheus/Grafana dashboards, and Kubernetes manifests are left as placeholders — see `gateway/`, `prometheus/`, and `k8s/` for notes on each.

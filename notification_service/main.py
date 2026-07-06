#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# notification_service/main.py
from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import urlparse

import pika
from dotenv import find_dotenv, load_dotenv
from loguru import logger

# Load env file
_ = load_dotenv(find_dotenv())

# Parse env variable
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "")
EVENTS_EXCHANGE = "claimmesh.events"
QUEUE_NAME = "notification_service.events"
ROUTING_KEYS = ["upload.completed", "fraud.flagged"]


logger.remove()
logger.add(sys.stdout, level=os.environ.get("LOG_LEVEL", "INFO"))


def _handle_upload_completed(payload: dict) -> None:
    """
    Log a notification for a finished upload batch. Stub — no real email/SMS delivery.
    """
    summary = payload.get("summary", {})

    logger.info(
        f"[notification] Upload batch {payload.get('task_id')} completed — "
        f"total={summary.get('total_records')} inserted={summary.get('inserted')} "
        f"rejected={summary.get('rejected')}"
    )


def _handle_fraud_flagged(payload: dict) -> None:
    """
    Log a notification for a customer newly flagged as potential fraud.
    """
    logger.info(f"[notification] Customer flagged as Potential Fraud: {payload.get('customer_id')}")


HANDLERS = {"upload.completed": _handle_upload_completed, "fraud.flagged": _handle_fraud_flagged}


def on_message(channel, method, properties, body: bytes) -> None:
    try:
        payload = json.loads(body.decode("utf-8"))
        handler = HANDLERS.get(method.routing_key)
        if handler:
            _ = handler(payload)
        else:
            logger.warning(f"No handler for routing key '{method.routing_key}'")
    except Exception as exc:
        logger.error(f"Failed to process message with routing key '{method.routing_key}': {exc}")
    finally:
        _ = channel.basic_ack(delivery_tag=method.delivery_tag)


def _connect_with_retry(retries: int = 10, delay: float = 3.0) -> pika.BlockingConnection:
    """
    Retry connecting to RabbitMQ so this service can start before the broker is ready
    (e.g. first `docker compose up`).
    """
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"RABBITMQ_URL={RABBITMQ_URL!r}")

            parsed = urlparse(RABBITMQ_URL)

            credentials = pika.PlainCredentials(
                username=parsed.username or "guest",
                password=parsed.password or "guest",
            )

            parameters = pika.ConnectionParameters(
                host=parsed.hostname or "rabbitmq",
                port=parsed.port or 5672,
                virtual_host="/",
                credentials=credentials,
                heartbeat=60,
               blocked_connection_timeout=30,
            )

            logger.info(f"host={parameters.host}, port={parameters.port}, virtual_host={parameters.virtual_host!r}")

            return pika.BlockingConnection(parameters)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(f"RabbitMQ connection failed (attempt {attempt}/{retries}): {exc}")
            _ = time.sleep(delay)

    raise RuntimeError("Could not connect to RabbitMQ") from last_exc


def main() -> None:
    """
    Connect to RabbitMQ, declare the shared topic exchange, and consume domain events.

    Runs as a plain pika consumer — deliberately not a Celery worker — so it is a fully
    independent process that the backend/worker services have no knowledge of.
    """
    connection = _connect_with_retry()
    channel = connection.channel()

    channel.exchange_declare(exchange=EVENTS_EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    for routing_key in ROUTING_KEYS:
        channel.queue_bind(exchange=EVENTS_EXCHANGE, queue=QUEUE_NAME, routing_key=routing_key)

    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)

    logger.info(f"notification_service listening on '{EVENTS_EXCHANGE}' for {ROUTING_KEYS}")

    try:
        channel.start_consuming()

    except KeyboardInterrupt:
        channel.stop_consuming()

    finally:
        connection.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# worker/tasks.py
"""
Celery worker tasks: full upload-batch ingestion (customers -> policies -> claims) and
fraud-flag recomputation. Reflects the schema created by backend/alembic migrations at
startup rather than redefining it, so worker and backend never drift on table shape.
"""
from __future__ import annotations

import io
import json
import os
import time
from base64 import b64decode
from urllib.parse import urlparse

import pandas as pd
import pika
import sqlalchemy as sa
from celery import Celery
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from sqlalchemy.dialects.postgresql import insert as pg_insert

from payout import calculate_payout
from validation import clean_claims, clean_customers, clean_policies


# Load .env file
_ = load_dotenv(find_dotenv())


# Get env variables
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")
EVENTS_EXCHANGE = "claimmesh.events"

celery_app = Celery("claimmesh", broker=RABBITMQ_URL, backend=REDIS_URL)

_ = celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

engine   = sa.create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
metadata = sa.MetaData()


def _reflect_table(name: str, retries: int = 10, delay: float = 3.0) -> sa.Table:
    """
    Reflect a table created by backend/alembic migrations. Retries so the worker can start
    before migrations have necessarily run (e.g. first `docker compose up`).
    """
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            return sa.Table(name, metadata, autoload_with=engine)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Reflecting table '{name}' failed (attempt {attempt}/{retries}): {exc}")
            time.sleep(delay)

    raise RuntimeError(f"Could not reflect table '{name}' after {retries} attempts") from last_exc


customers_table     = _reflect_table("customers")
policies_table      = _reflect_table("policies")
claims_table        = _reflect_table("claims")
upload_audits_table = _reflect_table("upload_audits")


def _decode(b64_str: str) -> bytes:
    return b64decode(b64_str)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert a cleaned DataFrame to a list of dicts, turning NaN/NaT into None so nullable
    DB columns (e.g. claims.payout_amount) don't get a literal NaN.
    """
    return df.astype(object).where(pd.notnull(df), None).to_dict("records")


def _bulk_insert_ignore_conflicts(conn, table: sa.Table, records: list[dict], pk_col: str) -> int:
    """
    Insert records, skipping rows that violate the primary key (idempotent re-uploads).
    Returns the number of rows actually inserted.
    """
    if not records:
        return 0
    stmt = pg_insert(table).values(records).on_conflict_do_nothing(index_elements=[pk_col])
    result = conn.execute(stmt)
    return result.rowcount or 0


def _record_audit(conn, dataset: str, total: int, inserted: int, rejected: int, errors: list[str], task_id: str) -> None:
    _ = conn.execute(
        upload_audits_table.insert().values(
            dataset=dataset,
            total_records=total,
            inserted=inserted,
            rejected=rejected,
            errors=errors,
            celery_task_id=task_id,
        )
    )


def _publish_event(routing_key: str, payload: dict) -> None:
    """
    Publish a durable domain event to the 'claimmesh.events' topic exchange.

    This publisher intentionally creates its own short-lived RabbitMQ connection.
    A failure to publish must never fail the ingestion transaction, so all
    connection/publish errors are treated as best-effort and only logged.
    """
    connection: pika.BlockingConnection | None = None

    try:
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

        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EVENTS_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )

        channel.basic_publish(
            exchange=EVENTS_EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(payload, default=str).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # Persistent message
            ),
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to publish event '{routing_key}': {exc}")

    finally:
        if connection and connection.is_open:
            connection.close()


@celery_app.task(name="process_upload_batch", bind=True)
def process_upload_batch(self, customers_b64: str, policies_b64: str, claims_b64: str) -> dict:
    """
    Clean and insert customers -> policies -> claims, in that dependency order, within a
    single DB transaction. Records a per-dataset upload_audits row, triggers a fraud-flag
    recompute, and publishes an 'upload.completed' event for notification_service.
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting upload batch")

    summary = {"total_records": 0, "inserted": 0, "rejected": 0, "errors": [], "datasets": {}}

    with engine.begin() as conn:
        # ---- customers ----
        customers_df = pd.read_csv(io.BytesIO(_decode(customers_b64)))
        clean_customers_df, customer_errors = clean_customers(customers_df)
        inserted_customers = _bulk_insert_ignore_conflicts(conn, customers_table, _df_to_records(clean_customers_df), "customer_id")
        _ = _record_audit(conn, "customers", len(customers_df), inserted_customers, len(customer_errors), customer_errors, task_id)

        summary["datasets"]["customers"] = {"total_records": len(customers_df), "inserted": inserted_customers, "rejected": len(customer_errors)}
        summary["total_records"] += len(customers_df)
        summary["inserted"] += inserted_customers
        summary["rejected"] += len(customer_errors)
        summary["errors"].extend(customer_errors)

        known_customer_ids = {row.customer_id for row in conn.execute(sa.select(customers_table.c.customer_id))}

        # ---- policies ----
        policies_df = pd.read_csv(io.BytesIO(_decode(policies_b64)))
        clean_policies_df, policy_errors = clean_policies(policies_df, known_customer_ids)
        inserted_policies = _bulk_insert_ignore_conflicts(conn, policies_table, _df_to_records(clean_policies_df), "policy_id")
        _ = _record_audit(conn, "policies", len(policies_df), inserted_policies, len(policy_errors), policy_errors, task_id)

        summary["datasets"]["policies"] = {"total_records": len(policies_df), "inserted": inserted_policies, "rejected": len(policy_errors)}
        summary["total_records"] += len(policies_df)
        summary["inserted"] += inserted_policies
        summary["rejected"] += len(policy_errors)
        summary["errors"].extend(policy_errors)

        policy_rows = conn.execute(
            sa.select(
                policies_table.c.policy_id,
                policies_table.c.coverage_limit,
                policies_table.c.deductible,
                policies_table.c.state,
                policies_table.c.policy_issue_date,
                customers_table.c.age.label("customer_age"),
            ).select_from(
                policies_table.join(customers_table, policies_table.c.customer_id == customers_table.c.customer_id)
            )
        )

        known_policy_map = {
            row.policy_id: {
                "coverage_limit": row.coverage_limit,
                "deductible": row.deductible,
                "state": row.state,
                "policy_issue_date": row.policy_issue_date,
                "customer_age": row.customer_age,
            }
            for row in policy_rows
        }

        # ---- claims ----
        claims_df = pd.read_csv(io.BytesIO(_decode(claims_b64)))
        clean_claims_df, claim_errors = clean_claims(claims_df, known_policy_map)
        inserted_claims = _bulk_insert_ignore_conflicts(conn, claims_table, _df_to_records(clean_claims_df), "claim_id")
        _ = _record_audit(conn, "claims", len(claims_df), inserted_claims, len(claim_errors), claim_errors, task_id)

        summary["datasets"]["claims"] = {"total_records": len(claims_df), "inserted": inserted_claims, "rejected": len(claim_errors)}
        summary["total_records"] += len(claims_df)
        summary["inserted"] += inserted_claims
        summary["rejected"] += len(claim_errors)
        summary["errors"].extend(claim_errors)

    _ = recompute_fraud_flags.delay()

    _ = _publish_event(
        "upload.completed",
        {"task_id": task_id, "summary": {k: v for k, v in summary.items() if k != "errors"}}
    )

    logger.info(
        f"[{task_id}] Upload batch finished: total={summary['total_records']} "
        f"inserted={summary['inserted']} rejected={summary['rejected']}"
    )

    return summary


@celery_app.task(name="recompute_fraud_flags")
def recompute_fraud_flags() -> dict:
    """
    flag customers with more than 5 valid claims as Potential Fraud.
    """
    with engine.begin() as conn:
        fraud_query = sa.text(
            """
            SELECT p.customer_id, COUNT(*) AS claim_count
            FROM claims c
            JOIN policies p ON p.policy_id = c.policy_id
            WHERE c.status = 'valid'
            GROUP BY p.customer_id
            HAVING COUNT(*) > 5
            """
        )

        fraud_customer_ids = [row.customer_id for row in conn.execute(fraud_query)]

        _ = conn.execute(
            customers_table
            .update()
            .values(is_potential_fraud=False)
        )

        if fraud_customer_ids:
            _ = conn.execute(
                customers_table.update()
                .where(customers_table.c.customer_id.in_(fraud_customer_ids))
                .values(is_potential_fraud=True)
            )

    for customer_id in fraud_customer_ids:
        _ = _publish_event("fraud.flagged", {"customer_id": customer_id})

    _ = logger.info(f"Fraud flag recompute complete. Flagged customers: {fraud_customer_ids}")
    return {"flagged_customers": fraud_customer_ids}

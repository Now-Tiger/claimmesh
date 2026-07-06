#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/services/taskservice.py
"""
Enqueue Celery tasks on the worker service and poll their status.

Assumes `utils/clients.py` exposes `celery_app = Celery("claimmesh", broker=..., backend=...)`
pointed at the same RabbitMQ/Redis instances the worker service uses.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from utils.clients import celery_app

UPLOAD_TASK_NAME = "process_upload_batch"


def enqueue_upload(customers_b64: str, policies_b64: str, claims_b64: str) -> str:
    """
    Enqueue the full customers -> policies -> claims ingestion pipeline on the worker.
    Returns the Celery task id used to poll status via `get_task_status`.
    """
    async_result = celery_app.send_task(UPLOAD_TASK_NAME, args=[customers_b64, policies_b64, claims_b64])
    _ = logger.info(f"Enqueued upload batch task {async_result.id}")
    return async_result.id


def get_task_status(task_id: str) -> dict[str, Any]:
    """Poll the status/result of a previously enqueued upload task."""
    async_result = celery_app.AsyncResult(task_id)
    payload: dict[str, Any] = {"task_id": task_id, "state": async_result.state}

    if async_result.state == "SUCCESS":
        payload["result"] = async_result.result

    elif async_result.state == "FAILURE":
        payload["error"] = str(async_result.result)

    return payload


def get_upload_result_sync(customers_b64: str, policies_b64: str, claims_b64: str, timeout: int = 120) -> dict[str, Any]:
    """Enqueue and block until the upload batch finishes. Used by POST /upload?sync=true."""
    async_result = celery_app.send_task(UPLOAD_TASK_NAME, args=[customers_b64, policies_b64, claims_b64])
    return async_result.get(timeout=timeout)

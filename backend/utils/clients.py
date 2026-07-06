#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/utils/client.py
from __future__ import annotations

from celery import Celery

from core.config import settings

RABBITMQ_URL = settings.RABBITMQ_URL
REDIS_URL = settings.REDIS_URL

celery_app = Celery(
    "claimmesh",
    broker=RABBITMQ_URL,
    backend=REDIS_URL,
)

_ = celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

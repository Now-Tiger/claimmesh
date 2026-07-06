#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/api/routers/health.py
from __future__ import annotations

import time
from datetime import timedelta

from fastapi import APIRouter
from loguru import logger
from sqlalchemy import text

from db.base import engine


router = APIRouter(tags=["Health"])


_START_TIME = time.time()


def _format_uptime(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m"


@router.get(
    "/health",
    summary="Check API and database health",
    response_description="API status, database connectivity, and process uptime",
)
async def health_check():
    """Verify the API process is responsive and the database is reachable via `SELECT 1`.
    Does not require authentication and is excluded from request-logging noise."""
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            _ = conn.execute(text("SELECT 1"))
    except Exception as exc:
        _ = logger.error(f"Health check DB connectivity failed: {exc}")
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "uptime": _format_uptime(time.time() - _START_TIME),
    }

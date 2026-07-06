#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/core/logging.py
from __future__ import annotations
import sys

from loguru import logger

from core.config import settings


def setup_logging() -> None:
    """
    Configure loguru: structured JSON to stdout plus a rotating file sink.
    Never log request bodies — only IDs/paths/status codes are logged from main.py.
    """
    _ = logger.remove()
    _ = logger.add(sys.stdout, level=settings.LOG_LEVEL, serialize=True, backtrace=False, diagnose=False)
    _ = logger.add(
        "logs/claimmesh-backend.log",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        serialize=True,
    )

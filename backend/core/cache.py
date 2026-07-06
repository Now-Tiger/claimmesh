#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/core/cache.py
from __future__ import annotations

import functools
import hashlib
import json
from typing import Callable, Optional

import redis.asyncio as redis
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from loguru import logger

from core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

CACHE_KEY_PREFIX = "claimmesh:cache"


def _build_cache_key(request: Request) -> str:
    """
    Derive a cache key from the request path + query string, namespaced by the first
    path segment (e.g. 'claims', 'customers', 'reports') so keys can be invalidated by group.
    """
    tag = request.url.path.strip("/").split("/")[0] or "root"
    raw = f"{request.url.path}?{str(request.query_params)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}:{tag}:{digest}"


def cached(ttl: int = 60):
    """
    Decorator for async FastAPI endpoints that caches the JSON-serializable return value in
    Redis. The decorated endpoint must accept a `request: Request` parameter.

    Cache invalidation strategy: TTL-only (no explicit bust on upload). Upload processing
    happens in the worker service and typically completes on a timescale close to or longer
    than these TTLs, so a short TTL expiry is simpler and safe enough for this workload rather
    than wiring cross-service cache invalidation.

    Fails open: any Redis error is logged and the endpoint executes normally.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                return await func(*args, **kwargs)

            cache_key = _build_cache_key(request)

            try:
                cached_value = await redis_client.get(cache_key)
                if cached_value is not None:
                    logger.info(f"Cache hit: {request.url.path}")
                    return json.loads(cached_value)
            except Exception as exc:
                logger.warning(f"Cache read failed for {cache_key}: {exc}")

            result = await func(*args, **kwargs)

            try:
                await redis_client.set(cache_key, json.dumps(jsonable_encoder(result)), ex=ttl)
            except Exception as exc:
                logger.warning(f"Cache write failed for {cache_key}: {exc}")

            return result

        return wrapper

    return decorator


async def invalidate_cache_group(tag: str) -> None:
    """
    Delete all cached keys under a given tag (e.g. 'claims', 'customers', 'reports').
    Not currently wired to any route (see TTL-only strategy above); available for future use.
    """
    try:
        pattern = f"{CACHE_KEY_PREFIX}:{tag}:*"
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)
    except Exception as exc:
        logger.warning(f"Cache invalidation failed for tag '{tag}': {exc}")

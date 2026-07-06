#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/core/security.py
from __future__ import annotations

from typing import Annotated

import secrets
from fastapi import Depends, Header, HTTPException, status

from core.config import settings


async def verify_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str:
    """
    Validate the caller's API key.

    This dependency is intended to be attached at the router level so every
    protected endpoint is secured by default, while explicitly public routes
    (e.g. /health) remain unauthenticated.

    Expected request header:
        X-API-Key: <api-key>

    Raises:
        HTTPException(401): Missing or invalid API key.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    FastAPI dependency enforcing a static API key on protected routes.
    Missing or incorrect keys both result in 401
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


# Reusable dependency alias for router-level protection.
APIKeyAuth = Depends(verify_api_key)

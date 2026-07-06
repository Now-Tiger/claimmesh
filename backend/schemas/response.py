#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/schemas/response.py
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ResponseModel(BaseModel):
    """
    Standard success response envelope returned by all API endpoints.
    """

    status: str = Field(..., examples=["success"])
    node: str = Field(..., examples=["backend-pod-01"])
    metadata: Optional[dict[str, Any]] = Field(default=None)


class ErrorResponse(BaseModel):
    """
    Standard error envelope used across the API.

    Note: this is the minimal shape needed for Phases 4-6. Phase 11 wires this up to global
    FastAPI exception handlers (RequestValidationError, NotFoundError, ConflictError, 500s) so
    every endpoint returns this exact shape consistently.
    """

    error: str = Field(..., examples=["ValidationError"])
    message: str = Field(..., examples=["Policy ID does not exist"])

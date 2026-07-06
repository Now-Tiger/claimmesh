#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/core/exceptions.py
from __future__ import annotations

from fastapi import HTTPException, status


class ApplicationException(HTTPException):
    """
    Base application exception.

    All domain-specific exceptions inherit from this class so they can be
    handled uniformly by FastAPI's global exception handlers.
    """

    def __init__(self, *, status_code: int, error: str, message: str) -> None:
        self.error = error

        super().__init__(
            status_code=status_code,
            detail=message,
        )


class BadRequestError(ApplicationException):
    """400 Bad Request."""

    def __init__(self, message: str = "Bad request.") -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="BadRequest",
            message=message,
        )


class UnauthorizedError(ApplicationException):
    """401 Unauthorized."""

    def __init__(self, message: str = "Unauthorized.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized",
            message=message,
        )


class ForbiddenError(ApplicationException):
    """403 Forbidden."""

    def __init__(self, message: str = "Forbidden.") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error="Forbidden",
            message=message,
        )


class NotFoundError(ApplicationException):
    """404 Resource Not Found."""

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error="NotFound",
            message=message,
        )


class ConflictError(ApplicationException):
    """409 Conflict."""

    def __init__(self, message: str = "Resource already exists.") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error="Conflict",
            message=message,
        )


class UnprocessableEntityError(ApplicationException):
    """422 Unprocessable Entity."""

    def __init__(self, message: str = "Request could not be processed.") -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="UnprocessableEntity",
            message=message,
        )


class InternalServerError(ApplicationException):
    """500 Internal Server Error."""

    def __init__(self, message: str = "Internal server error.") -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="InternalServerError",
            message=message,
        )

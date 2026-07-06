#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration, sourced from environment variables / .env file.
    """

    API_KEY: str
    LOG_LEVEL: str
    REDIS_URL: str
    RABBITMQ_URL: str
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# alembic/env.py

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import db.models
from alembic import context
from core.config import settings

# Base must be imported before models so the metadata object exists
from db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


# Inject the DATABASE_URL from our settings — overrides the blank value in alembic.ini
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline mode: generates a SQL script without a live DB connection.
    Useful for reviewing migration SQL before applying it.
    """
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        _ = context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        _ = context.run_migrations()


async def run_async_migrations() -> None:
    """
    Online mode: connects to the DB and applies migrations.
    NullPool is mandatory here — Alembic migration contexts must not share
    connections with the application pool.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        _ = await connection.run_sync(do_run_migrations)

    _ = await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in online mode using standard asyncio.run().
    This eliminates the Python 3.10+ event loop RuntimeError!
    """
    _ = asyncio.run(run_async_migrations())


if context.is_offline_mode():
    _ = run_migrations_offline()
else:
    _ = run_migrations_online()

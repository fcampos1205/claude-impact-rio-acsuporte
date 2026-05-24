"""Alembic async migration environment.

Uses SQLAlchemy 2.0 async engine pattern.
DATABASE_URL is read from app.config.settings.
All models must be imported via app.models to populate Base.metadata.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Load Alembic config
config = context.config

# Set up Python logging from the alembic.ini config section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and all models so metadata is populated
# IMPORTANT: All models must be imported here (or via __init__.py) for autogenerate to work
from app.models.base import Base  # noqa: E402
import app.models  # noqa: E402, F401  — side-effect: registers all tables on Base.metadata

# Override the sqlalchemy.url from alembic.ini with the value from settings
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (required for asyncpg)."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

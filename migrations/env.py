import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app import db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    # keep loggers made before this runs (the tests migrate in-process)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# The URL and the metadata come from app/db.py: migrations and the app use the same database.
target_metadata = db.Base.metadata


def run_migrations_offline() -> None:
    """Print the SQL and connect to nothing (`alembic upgrade head --sql`)."""
    context.configure(
        url=db.engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    async with db.engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await db.engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Alembic environment. Requires explicit PostgreSQL connection configuration."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.postgres import Base
from backend.app import models  # noqa: F401 - register mapped tables

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    raise RuntimeError("Offline migration disabled: use a dedicated test database")


def run_migrations_online():
    import os
    url = os.getenv("NEXIS_DATABASE_URL")
    if not url or not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Set NEXIS_DATABASE_URL to a dedicated PostgreSQL test database")
    cfg = config.get_section(config.config_ini_section)
    cfg["sqlalchemy.url"] = url
    engine = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

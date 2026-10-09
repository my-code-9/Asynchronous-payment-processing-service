from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
from app.db.database import Base

# Import all models
from app.models.payment import Payment
from app.models.outbox import Outbox

config = context.config

# Force Alembic to use psycopg (sync driver)
sync_url = settings.database_url.replace(
    "postgresql+asyncpg://",
    "postgresql+psycopg://",
)

config.set_main_option(
    "sqlalchemy.url",
    sync_url,
)

print("=" * 80)
print("DATABASE_URL from settings:")
print(settings.database_url)
print("=" * 80)

print("=" * 80)
print("ALEMBIC URL:")
print(config.get_main_option("sqlalchemy.url"))
print("=" * 80)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
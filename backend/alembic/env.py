import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import model as mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other options


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        config.get_section(config.config_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    connection = engine.connect()
    context.configure(
        connection=connection, target_metadata=target_metadata
    )

    with context.begin_transaction():
        context.run_migrations()
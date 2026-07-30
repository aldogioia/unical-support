from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# ✅ aggiungi user agli import — era mancante
from app.models.user import User
from app.models.category import Category
from app.models.document import Document
from app.models.template import Template
from app.models.blacklist import Blacklist
from app.models.email import Email
from app.models.feedback import Feedback
from app.models.ai_settings import AISettings

# ✅ importiamo settings per leggere DATABASE_URL dal .env
from app.core.config import settings

# ✅ importiamo Base e tutti i modelli così Alembic li conosce
# è fondamentale importarli tutti, altrimenti non genera le migration
from app.db.database import Base

config = context.config

# ✅ sovrascriviamo l'url con quella dal nostro .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ puntiamo al metadata dei nostri modelli per l'autogenerazione
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
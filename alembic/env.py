from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.core.config import settings
from app.models.role import RoleEnum  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_role import UserRole  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.campus import Campus  # noqa: F401
from app.models.faculty import Faculty  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.specialty import Specialty  # noqa: F401
from app.models.report_assignment import ReportAssignment  # noqa: F401
from app.models.report_status_event import ReportStatusEvent  # noqa: F401
from app.models.technical import Diagnosis, WorkLog  # noqa: F401
from app.models.token import RefreshToken  # noqa: F401
from app.models.comment import Comment, CommentMention  # noqa: F401
from app.models.collaboration import ReportCollaboration  # noqa: F401
from app.models.evidence import ReportEvidence  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URL)

target_metadata = SQLModel.metadata


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
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

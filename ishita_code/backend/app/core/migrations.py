"""Small, explicit, additive migration runner for the current SQLAlchemy app.

The project predates a migration tool. This runner records revisions and only
performs additive schema work; it never drops, reseeds, or rewrites existing
application data. Run `python -m app.core.migrations` before a production
deployment after taking the normal database backup.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, inspect, text
from sqlalchemy.engine import Engine

from app.core.database import Base, engine
import app.models  # noqa: F401 - register all model metadata
from app.models.access import Invitation, PasswordResetToken


SCHEMA_MIGRATIONS = Table(
    "schema_migrations",
    MetaData(),
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime, nullable=False),
    Column("description", String(255), nullable=False),
)


def _create_access_workflow_tables(target: Engine) -> None:
    Invitation.__table__.create(bind=target, checkfirst=True)
    PasswordResetToken.__table__.create(bind=target, checkfirst=True)


MIGRATIONS = [
    (1, "add invitation and password-reset workflow tables", _create_access_workflow_tables),
]


def migrate(target: Engine = engine) -> list[int]:
    """Apply outstanding additive revisions and return their version numbers."""
    # A new installation gets the complete current model schema once, through
    # this explicit command rather than application import side effects.
    if not inspect(target).get_table_names():
        Base.metadata.create_all(bind=target)

    SCHEMA_MIGRATIONS.create(bind=target, checkfirst=True)
    with target.begin() as connection:
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}

    completed: list[int] = []
    for version, description, operation in MIGRATIONS:
        if version in applied:
            continue
        operation(target)
        with target.begin() as connection:
            connection.execute(
                SCHEMA_MIGRATIONS.insert().values(
                    version=version,
                    applied_at=datetime.now(timezone.utc),
                    description=description,
                )
            )
        completed.append(version)
    return completed


def verify_schema(target: Engine = engine) -> None:
    present = set(inspect(target).get_table_names())
    expected = set(Base.metadata.tables) | {"schema_migrations"}
    missing = sorted(expected - present)
    if missing:
        raise RuntimeError(
            "Database schema is not current; missing tables: "
            + ", ".join(missing)
            + ". Run `python -m app.core.migrations` before starting the API."
        )


if __name__ == "__main__":
    applied = migrate()
    print("Applied migrations: " + (", ".join(map(str, applied)) if applied else "none (already current)"))

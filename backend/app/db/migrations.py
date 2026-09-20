"""Small-prototype migration contract.

Schema version 1 is created idempotently through SQLAlchemy metadata. A production rollout
would replace this module with Alembic revisions while preserving the same models.
"""

from app.db.database import init_db

SCHEMA_VERSION = 3


def migrate() -> int:
    init_db()
    return SCHEMA_VERSION

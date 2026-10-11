"""
Bring the database schema up to date (used by kubernetes/migrate-job.yaml).

Safe on three kinds of database:
  - empty:                          runs every migration
  - already migrated:               applies only the new ones
  - created by the old create_tables.py (tables exist, no alembic_version table):
                                    stamps it as revision 0001 first, then upgrades
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `import app` works

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings  # noqa: E402


async def _existing_tables() -> set[str]:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def main() -> None:
    tables = asyncio.run(_existing_tables())
    cfg = Config("alembic.ini")
    if "users" in tables and "alembic_version" not in tables:
        print("Existing schema without migration history: stamping revision 0001")
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")
    print("Database schema is up to date")


if __name__ == "__main__":
    main()

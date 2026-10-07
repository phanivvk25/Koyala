"""Run database migrations: python -m koyala.db.migrate (uses KOYALA_DATABASE_URL)."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


if __name__ == "__main__":
    upgrade(os.environ["KOYALA_DATABASE_URL"])

from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from app.core.models import Base

DB_PATH = Path("./data").resolve()
DB_PATH.mkdir(parents=True, exist_ok=True)
SQLITE_URL = f"sqlite:///{(DB_PATH / 'bot.db').as_posix()}"

engine = create_engine(SQLITE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _ensure_column(conn, table: str, column: str, ddl: str) -> None:
    """Lightweight SQLite migration helper."""
    cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        conn.commit()


def bootstrap() -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Lightweight migrations for additive schema changes
    with engine.connect() as conn:
        _ensure_column(conn, "redeems", "cooldown_s", "cooldown_s INTEGER NOT NULL DEFAULT 0")

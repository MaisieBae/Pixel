from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path

DB_PATH = Path("./data").resolve()
DB_PATH.mkdir(parents=True, exist_ok=True)
SQLITE_URL = f"sqlite:///{(DB_PATH / 'bot.db').as_posix()}"

engine = create_engine(SQLITE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def bootstrap() -> None:
    # Minimal bootstrap placeholder; real models arrive in v1.1.0
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
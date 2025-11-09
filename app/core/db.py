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


def bootstrap() -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()
    # Create tables
    Base.metadata.create_all(bind=engine)

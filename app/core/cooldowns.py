from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.core.models import Cooldown


class CooldownService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def is_active(self, user_id: int, command: str) -> tuple[bool, float]:
        now = datetime.utcnow()
        cd = self.db.scalar(select(Cooldown).where(Cooldown.user_id == user_id, Cooldown.command == command))
        if not cd:
            return False, 0.0
        if cd.expires_at <= now:
            self.db.execute(delete(Cooldown).where(Cooldown.id == cd.id))
            self.db.commit()
            return False, 0.0
        remaining = (cd.expires_at - now).total_seconds()
        return True, remaining

    def set(self, user_id: int, command: str, seconds: int) -> None:
        now = datetime.utcnow()
        expires = now + timedelta(seconds=seconds)
        # Upsert behavior
        cd = self.db.scalar(select(Cooldown).where(Cooldown.user_id == user_id, Cooldown.command == command))
        if cd:
            cd.expires_at = expires
        else:
            self.db.add(Cooldown(user_id=user_id, command=command, expires_at=expires))
        self.db.commit()
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models import QueueItem


class QueueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(self, kind: str, payload: dict) -> int:
        item = QueueItem(kind=kind, payload_json=payload, status="pending")
        self.db.add(item)
        self.db.commit()
        return item.id

    def list(self, status: str | None = None) -> list[QueueItem]:
        stmt = select(QueueItem).order_by(QueueItem.id.desc())
        if status:
            stmt = stmt.where(QueueItem.status == status)
        return list(self.db.scalars(stmt))
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models import Redeem, User
from app.core.points import PointsService
from app.core.cooldowns import CooldownService
from app.core.queue import QueueService


DEFAULT_REDEEMS: list[tuple[str, str, int, bool]] = [
    ("tts", "Text-to-Speech", 25, True),
    ("pixel", "Pixel Reply", 50, True),
    ("sound", "Play Sound", 15, True),
    ("spin", "Prize Wheel Spin", 100, True),
]


class RedeemsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.points = PointsService(db)
        self.cooldowns = CooldownService(db)
        self.queue = QueueService(db)

    def seed_defaults(self) -> None:
        existing_keys = set(self.db.scalars(select(Redeem.key)))
        changed = False
        for key, name, cost, enabled in DEFAULT_REDEEMS:
            if key not in existing_keys:
                self.db.add(Redeem(key=key, display_name=name, cost=cost, enabled=enabled))
                changed = True
        if changed:
            self.db.commit()

    def list(self) -> list[Redeem]:
        return list(self.db.scalars(select(Redeem).order_by(Redeem.key)))

    def get(self, key: str) -> Redeem | None:
        return self.db.scalar(select(Redeem).where(Redeem.key == key))

    def upsert(self, key: str, display_name: str, cost: int, enabled: bool) -> Redeem:
        r = self.get(key)
        if r is None:
            r = Redeem(key=key, display_name=display_name, cost=cost, enabled=enabled)
            self.db.add(r)
        else:
            r.display_name = display_name
            r.cost = cost
            r.enabled = enabled
            r.updated_at = datetime.utcnow()
        self.db.commit()
        return r

    def toggle(self, key: str, enabled: bool) -> None:
        r = self.get(key)
        if not r:
            raise ValueError("Redeem not found")
        r.enabled = enabled
        r.updated_at = datetime.utcnow()
        self.db.commit()

    # --- Core redeem flow (no side effects yet, just accounting/queue) ---
    def redeem(self, user_name: str, key: str, cooldown_s: int = 0, queue_kind: str | None = None, payload: dict | None = None) -> dict:
        user = self.points.ensure_user(user_name)
        r = self.get(key)
        if not r or not r.enabled:
            raise ValueError("Redeem is disabled or missing")

        # cooldown check
        active, remaining = self.cooldowns.is_active(user.id, key)
        if active:
            return {"ok": False, "error": f"Cooldown active: {int(remaining)}s left"}

        # spend points
        try:
            self.points.spend(user.id, r.cost, reason=f"redeem:{key}")
        except ValueError:
            return {"ok": False, "error": "Insufficient points"}

        # set cooldown
        if cooldown_s > 0:
            self.cooldowns.set(user.id, key, cooldown_s)

        # enqueue action
        qid = None
        if queue_kind:
            qid = self.queue.enqueue(queue_kind, payload or {"user": user.name, "redeem": key})

        return {"ok": True, "user": user.name, "redeem": key, "queue_id": qid}
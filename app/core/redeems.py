from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Redeem
from app.core.points import PointsService
from app.core.cooldowns import CooldownService
from app.core.queue import QueueService
from app.core.config import Settings


@dataclass(frozen=True)
class RedeemDefault:
    key: str
    display_name: str
    cost: int
    enabled: bool
    cooldown_s: int = 0


# Defaults are intentionally conservative (cooldowns prevent spam).
# Admin can edit these values via v1.9.0.
DEFAULT_REDEEMS: list[RedeemDefault] = [
    RedeemDefault("tts", "Text-to-Speech", 25, True, 10),
    RedeemDefault("pixel", "Pixel Reply", 50, True, 20),
    RedeemDefault("sound", "Play Sound", 15, True, 5),
    RedeemDefault("spin", "Prize Wheel Spin", 100, True, 0),
    RedeemDefault("clip", "Save Clip", 0, True, 5),
]


class RedeemsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.points = PointsService(db)
        self.cooldowns = CooldownService(db)
        self.queue = QueueService(db)

    def seed_defaults(self, settings: Settings | None = None) -> None:
        """Ensure the default redeems exist.

        If settings is provided, we use it to set more accurate initial cooldowns for tts/pixel
        while still allowing admin to override later.
        """
        defaults = DEFAULT_REDEEMS

        if settings is not None:
            # Match prior behavior where !tts cooldown came from settings, and pixel was ~20s.
            # These only apply when creating missing records (does NOT overwrite admin values).
            patched: list[RedeemDefault] = []
            for d in defaults:
                if d.key == "tts":
                    patched.append(
                        RedeemDefault(
                            d.key,
                            d.display_name,
                            d.cost,
                            d.enabled,
                            max(1, int(getattr(settings, "TTS_COOLDOWN_SECONDS", d.cooldown_s) or d.cooldown_s)),
                        )
                    )
                else:
                    patched.append(d)
            defaults = patched

        for d in defaults:
            r = self.get(d.key)
            if r is None:
                self.db.add(
                    Redeem(
                        key=d.key,
                        display_name=d.display_name,
                        cost=int(d.cost),
                        enabled=bool(d.enabled),
                        cooldown_s=int(d.cooldown_s),
                    )
                )
        self.db.commit()

    def get(self, key: str) -> Redeem | None:
        return self.db.scalar(select(Redeem).where(Redeem.key == key))

    def list(self) -> list[Redeem]:
        return list(self.db.scalars(select(Redeem).order_by(Redeem.key.asc())))

    def toggle(self, key: str, enabled: bool) -> None:
        r = self.get(key)
        if r is None:
            raise ValueError("Redeem not found")
        r.enabled = bool(enabled)
        r.updated_at = datetime.utcnow()
        self.db.commit()

    def upsert(self, key: str, display_name: str, cost: int, enabled: bool, cooldown_s: int = 0) -> Redeem:
        r = self.get(key)
        if r is None:
            r = Redeem(
                key=key,
                display_name=display_name,
                cost=int(cost),
                enabled=bool(enabled),
                cooldown_s=int(cooldown_s or 0),
            )
            self.db.add(r)
        else:
            r.display_name = display_name
            r.cost = int(cost)
            r.enabled = bool(enabled)
            r.cooldown_s = int(cooldown_s or 0)
            r.updated_at = datetime.utcnow()
        self.db.commit()
        return r

    # --- Core redeem flow (accounting + optional queue) ---
    def redeem(
        self,
        user_name: str,
        key: str,
        cooldown_s: int | None = None,
        *,
        queue_kind: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        """Attempt to redeem `key` for `user_name`.

        - Validates enabled state
        - Enforces cooldown
        - Spends points
        - Sets cooldown
        - Optionally enqueues a queue item (e.g. kind='tts', 'pixel', 'sound', 'spin')

        cooldown_s:
          - If provided: overrides DB cooldown for this call (keeps old behavior possible)
          - If None: uses the DB field Redeem.cooldown_s
        """
        user = self.points.ensure_user(user_name)
        r = self.get(key)
        if not r or not r.enabled:
            return {"ok": False, "error": "Redeem disabled or missing"}

        effective_cd = int(r.cooldown_s or 0) if cooldown_s is None else int(cooldown_s)

        # cooldown check
        if effective_cd > 0:
            active, remaining = self.cooldowns.is_active(user.id, key)
            if active:
                return {"ok": False, "error": f"Cooldown active: {int(remaining)}s left"}

        # spend points
        try:
            self.points.spend(user.id, int(r.cost), reason=f"redeem:{key}")
        except ValueError:
            return {"ok": False, "error": "Insufficient points"}

        # set cooldown
        if effective_cd > 0:
            self.cooldowns.set(user.id, key, effective_cd)

        # enqueue action
        qid = None
        if queue_kind:
            qid = self.queue.enqueue(queue_kind, payload or {"user": user.name, "redeem": key})

        return {"ok": True, "user": user.name, "redeem": key, "queue_id": qid}

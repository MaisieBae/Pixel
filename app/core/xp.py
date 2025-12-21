from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.cooldowns import CooldownService
from app.core.models import User, XP, XPTransaction, QueueItem
from app.core.points import PointsService
from app.core.xp_curve import level_from_xp, progress_to_next_level
from app.core.xp_policy import XpEvent, normalize_event_type
from app.core.level_rewards import apply_level_rewards


@dataclass(frozen=True)
class XpAwardResult:
    ok: bool
    user_id: int
    user_name: str
    delta: int
    total_xp: int
    level_before: int
    level_after: int
    reason: str
    source: str
    reward_actions: list[dict[str, Any]]


class XpService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.points = PointsService(db)
        self.cooldowns = CooldownService(db)

    def ensure_user_xp(self, user_name: str) -> tuple[User, XP]:
        u = self.points.ensure_user(user_name)
        xp = self.db.get(XP, u.id)
        if xp is None:
            xp = XP(user_id=u.id, total_xp=0, level=1)
            self.db.add(xp)
            self.db.commit()
        return u, xp

    def get_progress_text(self, user_name: str) -> str:
        u, xp = self.ensure_user_xp(user_name)
        base = int(getattr(self.settings, "XP_BASE", 100) or 100)
        exponent = float(getattr(self.settings, "XP_EXPONENT", 1.8) or 1.8)
        into, required, ratio = progress_to_next_level(xp.total_xp, xp.level, base=base, exponent=exponent)
        pct = int(ratio * 100)
        return f"@{u.name} — Level {xp.level} • XP {xp.total_xp} • {into}/{required} ({pct}%)"

    def adjust(self, user_name: str, delta: int, *, reason: str = "admin_adjust", source: str = "admin") -> XpAwardResult:
        u, xp = self.ensure_user_xp(user_name)
        return self._award(u, xp, int(delta), reason=reason, source=source, bypass_cooldown=True)

    def handle_event(self, event: XpEvent) -> XpAwardResult | None:
        if not bool(getattr(self.settings, "XP_ENABLED", True)):
            return None

        et = normalize_event_type(event.type)
        user = (event.user or "").strip()
        if not user:
            return None

        # Map event → xp amount + cooldown key
        if et == "chat":
            amount = int(getattr(self.settings, "XP_CHAT_AMOUNT", 1) or 1)
            cd = int(getattr(self.settings, "XP_CHAT_COOLDOWN_SECONDS", 30) or 30)
            cooldown_key = "xp:chat"
        elif et == "follow":
            amount = int(getattr(self.settings, "XP_FOLLOW_AMOUNT", 10) or 10)
            cd = int(getattr(self.settings, "XP_FOLLOW_COOLDOWN_SECONDS", 3600) or 3600)
            cooldown_key = "xp:follow"
        elif et == "sub":
            months = int(event.metadata.get("months", 1) or 1)
            base_amt = int(getattr(self.settings, "XP_SUB_AMOUNT", 50) or 50)
            amount = max(0, base_amt * max(1, months))
            cd = int(getattr(self.settings, "XP_SUB_COOLDOWN_SECONDS", 3600) or 3600)
            cooldown_key = "xp:sub"
        elif et == "tip":
            tokens = int(event.metadata.get("tokens", 0) or 0)
            per = float(getattr(self.settings, "XP_TIP_PER_TOKEN", 0.1) or 0.1)
            amount = int(tokens * per)
            cd = int(getattr(self.settings, "XP_TIP_COOLDOWN_SECONDS", 30) or 30)
            cooldown_key = "xp:tip"
        elif et == "dropin":
            amount = int(getattr(self.settings, "XP_DROPIN_AMOUNT", 5) or 5)
            cd = int(getattr(self.settings, "XP_DROPIN_COOLDOWN_SECONDS", 3600) or 3600)
            cooldown_key = "xp:dropin"
        else:
            return None

        if amount <= 0:
            return None

        u, xp = self.ensure_user_xp(user)

        # cooldown check
        if cd > 0:
            active, _remaining = self.cooldowns.is_active(u.id, cooldown_key)
            if active:
                return None

        result = self._award(u, xp, amount, reason=et, source=event.source, bypass_cooldown=True)

        # Set cooldown after successful award
        if result.ok and cd > 0:
            self.cooldowns.set(u.id, cooldown_key, cd)

        return result

    def list_transactions(self, user_id: int, limit: int = 50) -> list[XPTransaction]:
        stmt = (
            select(XPTransaction)
            .where(XPTransaction.user_id == int(user_id))
            .order_by(XPTransaction.id.desc())
            .limit(max(1, int(limit)))
        )
        return list(self.db.scalars(stmt))

    def _award(
        self,
        user: User,
        xp: XP,
        delta: int,
        *,
        reason: str,
        source: str,
        bypass_cooldown: bool,
    ) -> XpAwardResult:
        # Ensure row is attached
        if xp.user_id != user.id:
            xp.user_id = user.id

        before_level = int(xp.level or 1)
        before_total = int(xp.total_xp or 0)

        new_total = max(0, before_total + int(delta))

        base = int(getattr(self.settings, "XP_BASE", 100) or 100)
        exponent = float(getattr(self.settings, "XP_EXPONENT", 1.8) or 1.8)
        new_level = int(level_from_xp(new_total, base=base, exponent=exponent, max_level=int(getattr(self.settings, "XP_MAX_LEVEL", 9999) or 9999)))

        xp.total_xp = int(new_total)
        xp.level = int(new_level)
        self.db.add(xp)

        tx = XPTransaction(user_id=user.id, delta=int(delta), reason=str(reason or ""), source=str(source or ""), created_at=datetime.utcnow())
        self.db.add(tx)

        reward_actions: list[dict[str, Any]] = []
        # Apply any rewards for each level crossed (e.g. jumping multiple levels)
        rewards_file = getattr(self.settings, "XP_LEVEL_REWARDS_FILE", "./data/level_rewards.json")
        if int(new_level) > int(before_level):
            for lvl in range(before_level + 1, new_level + 1):
                acts = apply_level_rewards(
                    self.db,
                    user_id=user.id,
                    user_name=user.name,
                    new_level=lvl,
                    rewards_path=rewards_file,
                )
                reward_actions.extend(acts)

                # If a reward requests a TTS line, enqueue it.
                for a in acts:
                    if a.get("type") == "tts":
                        self.db.add(
                            QueueItem(
                                kind="tts",
                                status="pending",
                                payload_json={"user": user.name, "message": str(a.get("text", "")), "prefix": False, "source": "level"},
                            )
                        )

        self.db.commit()

        return XpAwardResult(
            ok=True,
            user_id=user.id,
            user_name=user.name,
            delta=int(delta),
            total_xp=int(new_total),
            level_before=int(before_level),
            level_after=int(new_level),
            reason=str(reason or ""),
            source=str(source or ""),
            reward_actions=reward_actions,
        )
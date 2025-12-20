from __future__ import annotations

from typing import Any

from app.core.effects.engine import EffectHandler, EffectValidationError
from app.core.effects.types import EffectContext, EffectResult


class PointsGrantHandler(EffectHandler):
    type = "points.grant"

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        if not ctx.user:
            raise EffectValidationError("points.grant requires ctx.user")

        if ctx.db is None:
            raise EffectValidationError("points.grant requires ctx.db")

        amount = effect.get("amount")
        try:
            amount_i = int(amount)
        except Exception:
            raise EffectValidationError("points.grant.amount must be an int")

        reason = str(effect.get("reason") or ctx.source or "effect").strip()
        # Enrich reason with prize name if present
        if ctx.prize_name:
            reason = f"{reason}:{ctx.prize_name}"

        from app.core.points import PointsService

        ps = PointsService(ctx.db)
        urow = ps.ensure_user(ctx.user)
        new_balance = ps.grant(urow.id, amount=amount_i, reason=reason)

        return EffectResult(
            ok=True,
            type=self.type,
            detail={
                "user": ctx.user,
                "user_id": urow.id,
                "amount": amount_i,
                "reason": reason,
                "new_balance": new_balance,
            },
        )

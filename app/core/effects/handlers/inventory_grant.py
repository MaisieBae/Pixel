from __future__ import annotations

from typing import Any

from app.core.effects.engine import EffectHandler, EffectValidationError
from app.core.effects.types import EffectContext, EffectResult


class InventoryGrantHandler(EffectHandler):
    type = "inventory.grant"

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        if not ctx.user:
            raise EffectValidationError("inventory.grant requires ctx.user")
        if ctx.db is None:
            raise EffectValidationError("inventory.grant requires ctx.db")

        key = str(effect.get("key") or "").strip().lower()
        if not key:
            raise EffectValidationError("inventory.grant.key is required")

        qty = effect.get("qty", 1)
        try:
            qty_i = int(qty)
        except Exception:
            raise EffectValidationError("inventory.grant.qty must be an int")
        if qty_i == 0:
            raise EffectValidationError("inventory.grant.qty must be non-zero")

        from app.core.points import PointsService
        from app.core.items import ItemsService

        ps = PointsService(ctx.db)
        isvc = ItemsService(ctx.db)
        urow = ps.ensure_user(ctx.user)
        inv = isvc.grant_item(urow.id, key, qty=qty_i)

        return EffectResult(
            ok=True,
            type=self.type,
            detail={
                "user": ctx.user,
                "user_id": urow.id,
                "item_key": key,
                "qty_delta": qty_i,
                "new_qty": int(inv.qty),
            },
        )

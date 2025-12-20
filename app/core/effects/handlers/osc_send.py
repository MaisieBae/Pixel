from __future__ import annotations

from typing import Any

from app.core.effects.engine import EffectHandler, EffectValidationError
from app.core.effects.types import EffectContext, EffectResult


class OscSendHandler(EffectHandler):
    type = "osc.send"

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        if ctx.settings is None:
            raise EffectValidationError("osc.send requires ctx.settings")

        address = str(effect.get("address") or "").strip()
        if not address:
            raise EffectValidationError("osc.send.address is required")
        if not address.startswith("/"):
            raise EffectValidationError("osc.send.address must start with '/'")

        value_type = str(effect.get("value_type") or effect.get("type") or "int").strip()
        value = effect.get("value")

        from app.core.osc import OSCService, OscMessage

        osc = OSCService(ctx.settings)
        msg = OscMessage(address=address, type=value_type, value=value)
        osc.send_many([msg])

        return EffectResult(
            ok=True,
            type=self.type,
            detail={
                "address": address,
                "value_type": value_type,
                "value": value,
                "enabled": osc.enabled(),
            },
        )

from __future__ import annotations

from typing import Any

from app.core.effects.engine import EffectHandler, EffectValidationError
from app.core.effects.types import EffectContext, EffectResult


class ExtensionTriggerHandler(EffectHandler):
    type = "extension.trigger"

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        if ctx.db is None:
            raise EffectValidationError("extension.trigger requires ctx.db")

        action = effect.get("action")
        if not action:
            raise EffectValidationError("extension.trigger.action is required")

        # Create a queue item to trigger the extension
        from app.core.models import QueueItem

        payload = {
            "user": ctx.user or "wheel",
            "action": str(action)
        }

        q = QueueItem(
            kind='extension',
            status='pending',
            payload_json=payload
        )
        ctx.db.add(q)
        ctx.db.commit()

        return EffectResult(
            ok=True,
            type=self.type,
            detail={
                "action": action,
                "queued": True
            },
        )

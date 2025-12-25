from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.core.effects.types import EffectContext, EffectResult


class EffectValidationError(ValueError):
    pass


class EffectHandler:
    """Base class for effect handlers.

    Handlers should be small and focused. They may raise EffectValidationError
    for schema problems; other exceptions are treated as handler failures.
    """

    # the effect "type" this handler supports
    type: str = ""

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        raise NotImplementedError


@dataclass
class EffectEngine:
    """Executes effects via a registry of handlers."""

    db: Any
    settings: Any
    bus: Any
    
    def __post_init__(self) -> None:
        # Lazy import handlers to avoid side-effects at import time.
        from app.core.effects.handlers.inventory_grant import InventoryGrantHandler
        from app.core.effects.handlers.osc_send import OscSendHandler
        from app.core.effects.handlers.points_grant import PointsGrantHandler
        from app.core.effects.handlers.extension_trigger import ExtensionTriggerHandler

        self._handlers: dict[str, EffectHandler] = {}
        for h in (PointsGrantHandler(), InventoryGrantHandler(), ExtensionTriggerHandler(), OscSendHandler()):
            if h.type:
                self._handlers[h.type] = h

    def apply_all(self, effects: Iterable[dict[str, Any]], ctx: EffectContext) -> list[EffectResult]:
        """Apply a list of effects.

        Execution is best-effort: one failing effect does not stop the rest.
        """
        results: list[EffectResult] = []
        for eff in (effects or []):
            if not isinstance(eff, dict):
                results.append(
                    EffectResult(
                        ok=False,
                        type="invalid",
                        detail={"raw": str(eff)},
                        error="Effect is not an object",
                    )
                )
                continue

            t = str(eff.get("type") or "").strip()
            if not t:
                results.append(
                    EffectResult(ok=False, type="invalid", detail={"effect": eff}, error="Missing effect.type")
                )
                continue

            handler = self._handlers.get(t)
            if not handler:
                results.append(
                    EffectResult(ok=False, type=t, detail={"effect": eff}, error=f"No handler registered for {t}")
                )
                continue

            try:
                r = handler.apply(eff, ctx)
            except EffectValidationError as ve:
                r = EffectResult(ok=False, type=t, detail={"effect": eff}, error=str(ve))
            except Exception as e:
                r = EffectResult(ok=False, type=t, detail={"effect": eff}, error=f"Handler error: {e}")
            results.append(r)

        return results


def effects_from_prize(prize_obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize prize objects to a canonical effects list.

    Supports both:
      - New schema: {"effects": [ {"type": ...}, ... ]}
      - Legacy fields currently used by QueueWorker:
          grant_points, item_key/item_qty, osc
    """
    if not isinstance(prize_obj, dict):
        return []

    # Preferred schema
    effects = prize_obj.get("effects")
    if isinstance(effects, list):
        # Keep only dict entries
        return [e for e in effects if isinstance(e, dict)]

    out: list[dict[str, Any]] = []

    # Legacy: points
    gp = prize_obj.get("grant_points")
    if gp is not None:
        try:
            out.append({"type": "points.grant", "amount": int(gp), "reason": "wheel"})
        except Exception:
            # keep invalid input as a validation failure later
            out.append({"type": "points.grant", "amount": gp, "reason": "wheel"})

    # Legacy: inventory
    ik = (prize_obj.get("item_key") or "").strip().lower()
    if ik:
        out.append({"type": "inventory.grant", "key": ik, "qty": prize_obj.get("item_qty", 1)})

    # Legacy: osc
    osc_spec = prize_obj.get("osc")
    if isinstance(osc_spec, dict):
        # param style
        if osc_spec.get("param"):
            out.append(
                {
                    "type": "osc.send",
                    "address": f"/avatar/parameters/{osc_spec.get('param')}",
                    "value_type": str(osc_spec.get("type", "int")),
                    "value": osc_spec.get("value", 1),
                }
            )
        else:
            out.append(
                {
                    "type": "osc.send",
                    "address": osc_spec.get("address"),
                    "value_type": osc_spec.get("type"),
                    "value": osc_spec.get("value"),
                }
            )
    elif isinstance(osc_spec, list):
        for it in osc_spec:
            if not isinstance(it, dict):
                continue
            if it.get("param"):
                out.append(
                    {
                        "type": "osc.send",
                        "address": f"/avatar/parameters/{it.get('param')}",
                        "value_type": str(it.get("type", "int")),
                        "value": it.get("value", 1),
                    }
                )
            else:
                out.append(
                    {
                        "type": "osc.send",
                        "address": it.get("address"),
                        "value_type": it.get("type"),
                        "value": it.get("value"),
                    }
                )

    return out

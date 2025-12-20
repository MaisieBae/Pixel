"""Effect engine for applying prize/redeem outcomes.

Design goals:
 - Keep QueueWorker thin (no points/items/OSC logic).
 - Effects are declarative (JSON describes *what*, handlers implement *how*).
 - Handlers are small, testable units.
"""

from .engine import EffectEngine, effects_from_prize
from .types import EffectContext, EffectResult

__all__ = ["EffectEngine", "effects_from_prize", "EffectContext", "EffectResult"]

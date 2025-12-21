"""Core package.

Keep this file lightweight: importing `app.core` should not fail because of optional modules.

Effect system is implemented under `app.core.effects`.
"""

from .effects.engine import EffectEngine, effects_from_prize
from .effects.types import EffectContext, EffectResult

__all__ = ["EffectEngine", "effects_from_prize", "EffectContext", "EffectResult"]

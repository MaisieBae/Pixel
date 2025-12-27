from __future__ import annotations

from typing import Any

from app.core.effects.engine import EffectHandler, EffectValidationError
from app.core.effects.types import EffectContext, EffectResult


class SfxPlayHandler(EffectHandler):
    """Handler for playing sound effects via the overlay bus."""
    
    type = "sfx.play"

    async def apply_async(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        """Async version for sound playback."""
        if ctx.bus is None:
            raise EffectValidationError("sfx.play requires ctx.bus")

        sound = effect.get("sound")
        if not sound:
            raise EffectValidationError("sfx.play.sound is required")

        # Validate the sound exists (optional but recommended)
        if ctx.settings:
            try:
                from app.core.sfx import validate_sound_file
                validated = validate_sound_file(ctx.settings, str(sound))
                sound = validated
            except ValueError as e:
                raise EffectValidationError(f"Invalid sound: {e}")

        # Play the sound
        from app.core.sfx import play_sfx
        await play_sfx(ctx.bus, str(sound))

        return EffectResult(
            ok=True,
            type=self.type,
            detail={"sound": sound},
        )

    def apply(self, effect: dict[str, Any], ctx: EffectContext) -> EffectResult:
        """Sync wrapper - creates a task for async playback."""
        import asyncio
        
        # Create task but don't wait for it
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.apply_async(effect, ctx))
        
        # Return immediately with pending status
        return EffectResult(
            ok=True,
            type=self.type,
            detail={"sound": effect.get("sound"), "status": "queued"},
        )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class EffectContext:
    """Shared context passed to effect handlers."""

    # Who triggered the effect (typically a chat username)
    user: str

    # Source metadata (useful for audit reasons)
    source: str  # e.g. "wheel" | "redeem" | "admin"
    prize_name: str = ""

    # Infra/services
    db: Any = None
    settings: Any = None
    bus: Any = None


@dataclass
class EffectResult:
    """Structured handler output; safe to store in JSON."""

    ok: bool
    type: str
    detail: dict[str, Any]
    error: Optional[str] = None
    at_utc: str = ""

    def __post_init__(self) -> None:
        if not self.at_utc:
            # Keep as ISO string to remain JSON-serializable.
            self.at_utc = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "type": self.type,
            "detail": self.detail or {},
            "error": self.error,
            "at_utc": self.at_utc,
        }

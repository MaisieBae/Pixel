from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class XpEvent:
    """Stable internal event format for XP.

    Producers (Joystick ingest, sim console, future VRChat OSC) should emit this.
    The XP system consumes it without caring where it came from.
    """

    type: str  # chat|follow|sub|tip|dropin
    user: str
    metadata: Dict[str, Any]
    source: str = "joystick"  # joystick|sim|admin


def normalize_event_type(t: str) -> str:
    return (t or "").strip().lower()


def is_xp_eligible_chat(text: str, *, min_len: int = 1) -> bool:
    msg = (text or "").strip()
    if not msg:
        return False
    # Commands don't generate passive XP.
    if msg.startswith("!"):
        return False
    return len(msg) >= max(1, int(min_len))

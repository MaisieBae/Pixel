from __future__ import annotations

import math


def xp_total_for_level(level: int, *, base: int = 100, exponent: float = 1.8) -> int:
    """Cumulative XP required to be at `level`.

    Level 1 is the starting level and requires 0 XP.

    Curve:
      total_xp(level) = base * (level-1)^exponent

    Returns an integer (floored).
    """
    lvl = max(1, int(level))
    if lvl <= 1:
        return 0
    return int(math.floor(float(base) * math.pow(lvl - 1, float(exponent))))


def level_from_xp(total_xp: int, *, base: int = 100, exponent: float = 1.8, max_level: int = 9999) -> int:
    """Compute current level from cumulative XP.

    This uses a fast approximation and then corrects by stepping.
    """
    tx = max(0, int(total_xp))
    if tx <= 0:
        return 1

    b = max(1, int(base))
    e = max(0.25, float(exponent))

    # Invert: tx = b*(L-1)^e  =>  L = 1 + (tx/b)^(1/e)
    approx = 1 + int(math.floor(math.pow(tx / b, 1.0 / e)))
    lvl = max(1, min(int(approx), int(max_level)))

    # Correct off-by-a-few errors caused by flooring.
    while lvl < max_level and xp_total_for_level(lvl + 1, base=b, exponent=e) <= tx:
        lvl += 1
    while lvl > 1 and xp_total_for_level(lvl, base=b, exponent=e) > tx:
        lvl -= 1

    return lvl


def progress_to_next_level(total_xp: int, level: int, *, base: int = 100, exponent: float = 1.8) -> tuple[int, int, float]:
    """Return (current_into_level, required_this_level, ratio)."""
    lvl = max(1, int(level))
    tx = max(0, int(total_xp))

    cur_threshold = xp_total_for_level(lvl, base=base, exponent=exponent)
    next_threshold = xp_total_for_level(lvl + 1, base=base, exponent=exponent)
    required = max(1, int(next_threshold - cur_threshold))
    into = max(0, int(tx - cur_threshold))
    ratio = min(1.0, max(0.0, into / required))
    return into, required, ratio

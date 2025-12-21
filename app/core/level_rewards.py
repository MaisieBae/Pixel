from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.items import ItemsService
from app.core.points import PointsService


@dataclass(frozen=True)
class LevelReward:
    level: int
    points: int = 0
    items: dict[str, int] | None = None
    tts: str | None = None


def _parse_reward(obj: dict[str, Any]) -> LevelReward | None:
    try:
        lvl = int(obj.get("level", 0))
        if lvl <= 0:
            return None
        points = int(obj.get("points", 0) or 0)
        items = obj.get("items")
        if not isinstance(items, dict):
            items = None
        else:
            # coerce qty to int
            items = {str(k): int(v) for k, v in items.items()}
        tts = obj.get("tts")
        if tts is not None:
            tts = str(tts)
        return LevelReward(level=lvl, points=points, items=items, tts=tts)
    except Exception:
        return None


def load_level_rewards(path: str | Path) -> dict[int, LevelReward]:
    """Load level-up rewards from JSON.

    File format (list):
      [
        {"level": 5, "points": 100},
        {"level": 10, "items": {"ticket": 1}, "tts": "{user} reached level {level}!"}
      ]

    Missing file => empty rewards.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, list):
        return {}

    out: dict[int, LevelReward] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        r = _parse_reward(item)
        if r is None:
            continue
        out[r.level] = r
    return out


def apply_level_rewards(
    db: Session,
    *,
    user_id: int,
    user_name: str,
    new_level: int,
    rewards_path: str | Path,
) -> list[dict[str, Any]]:
    """Apply any reward for `new_level`.

    Returns a list of applied actions for logging/debug.
    """
    rewards = load_level_rewards(rewards_path)
    r = rewards.get(int(new_level))
    if r is None:
        return []

    applied: list[dict[str, Any]] = []

    if int(r.points or 0) != 0:
        ps = PointsService(db)
        new_bal = ps.grant(user_id, amount=int(r.points), reason=f"level_reward:{new_level}")
        applied.append({"type": "points", "amount": int(r.points), "new_balance": int(new_bal)})

    if r.items:
        isvc = ItemsService(db)
        for key, qty in r.items.items():
            if int(qty) == 0:
                continue
            isvc.grant_item(user_id, str(key), qty=int(qty))
            applied.append({"type": "item", "key": str(key), "qty": int(qty)})

    if r.tts:
        applied.append({"type": "tts", "text": r.tts.format(user=user_name, level=new_level)})

    return applied

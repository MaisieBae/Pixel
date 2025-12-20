from __future__ import annotations
import json, random
from pathlib import Path
from typing import Any

from app.core.config import Settings


DEFAULT_PRIZES: list[dict[str, Any]] = [
    {"name": "50 Points", "weight": 30},
    {"name": "100 Points", "weight": 20},
    {"name": "Confetti Blast", "weight": 15},
    {"name": "Silly Honk", "weight": 15},
    {"name": "Streamer Compliment", "weight": 10},
    {"name": "Mystery Prize", "weight": 10},
]


def _read_lines(path: Path) -> list[str]:
    try:
        txt = path.read_text(encoding="utf-8")
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        return lines or [""]
    except Exception:
        return [""]


def load_spin_lines(settings: Settings) -> list[str]:
    return _read_lines(Path(settings.SPIN_LINES_FILE))


def load_prize_lines(settings: Settings) -> list[str]:
    return _read_lines(Path(settings.PRIZE_LINES_FILE))


def load_prizes(settings: Settings) -> list[dict[str, Any]]:
    p = Path(settings.PRIZES_FILE)
    if not p.exists():
        return DEFAULT_PRIZES
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        items: list[dict[str, Any]] = []
        for it in data:
            if not isinstance(it, dict):
                continue
            # Always keep name/weight, but allow extra fields like:
            #   grant_points, item_key, item_qty, osc
            name = str(it.get("name", "Prize"))
            weight = int(it.get("weight", 1))
            obj: dict[str, Any] = dict(it)
            obj["name"] = name
            obj["weight"] = max(1, weight)
            items.append(obj)
        return items or DEFAULT_PRIZES
    except Exception:
        return DEFAULT_PRIZES


def weighted_choice_index(items: list[dict[str, Any]]) -> int:
    weights = [max(1, int(it.get("weight", 1))) for it in items]
    idx = random.choices(range(len(items)), weights=weights, k=1)[0]
    return int(idx)

# Prize Wheel System

The Prize Wheel provides an interactive gambling mechanic where users spin for random rewards.

## Overview

Users spend points to spin the wheel, which selects a prize based on weighted probabilities. Prizes can include points, XP, items, special effects, or custom rewards.

## Configuration

```ini
PRIZES_FILE=./data/prizes.json
SPIN_LINES_FILE=./data/spin_lines.txt
PRIZE_LINES_FILE=./data/prize_lines.txt

WHEEL_SFX_START=wheel_start.wav
WHEEL_SFX_LOOP=wheel_loop.wav
WHEEL_SFX_WIN=wheel_win.wav

WHEEL_SPIN_MIN=2
WHEEL_SPIN_MAX=10
```

## Prizes Configuration

**Location**: `./data/prizes.json`

```json
[
  {
    "name": "50 Points",
    "weight": 30,
    "grant_points": 50
  },
  {
    "name": "100 Points",
    "weight": 20,
    "grant_points": 100
  },
  {
    "name": "1000 XP",
    "weight": 15,
    "grant_xp": 1000
  },
  {
    "name": "Confetti Blast",
    "weight": 15,
    "effect": "confetti"
  }
]
```

### Prize Fields

**Required**:
- `name` - Display name of prize
- `weight` - Probability weight (higher = more common)

**Optional**:
- `grant_points` - Points to award
- `grant_xp` - XP to award
- `effect` - Effect to trigger
- `custom` - Requires custom handler

## Probability System

| Prize | Weight | Probability |
|-------|--------|-------------|
| 50 Points | 30 | 30% |
| 100 Points | 20 | 20% |
| 1000 XP | 15 | 15% |
| Confetti | 15 | 15% |

## Prize Types

### Points Prize

```python
if "grant_points" in prize:
    amount = int(prize["grant_points"])
    points_service.grant(user_id, amount, reason="wheel_prize")
```

### XP Prize

```python
if "grant_xp" in prize:
    amount = int(prize["grant_xp"])
    xp_service.adjust(user_name, amount, reason="wheel_prize", source="wheel")
```

### Effect Prize

```python
if "effect" in prize:
    await trigger_effect(prize["effect"])
```

## Announcement Lines

**Spin Lines** (`./data/spin_lines.txt`):
```
{user} is spinning the wheel!
{user} takes a spin!
```

**Prize Lines** (`./data/prize_lines.txt`):
```
{user} won {prize}!
Congratulations {user}, you won {prize}!
```

## Sound Effects

- **Start Sound**: Plays once when wheel begins spinning
- **Loop Sound**: Repeats while spinning
- **Win Sound**: Plays when wheel stops

## Best Practices

### Prize Balance
1. **60-70%**: Small prizes
2. **20-30%**: Medium prizes
3. **5-10%**: Large prizes
4. **1-5%**: Jackpots

## See Also

- [Redeems System](redeems.md)
- [Points System](points-system.md)
- [Event Flow](event-flow.md)

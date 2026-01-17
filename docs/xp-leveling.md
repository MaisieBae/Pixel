# XP & Leveling System

The XP (Experience Points) and Leveling System provides a progressive achievement structure that rewards sustained engagement over time.

## Overview

Unlike the Points system (which is currency), XP is cumulative and never decreases. As users accumulate XP, they level up following a configurable growth curve. Level-ups can trigger rewards like bonus points, messages, or TTS announcements.

## Architecture

### Service Class: `XpService`

**Location**: `app/core/xp.py`

```python
class XpService:
    def ensure_user_xp(user_name: str) -> tuple[User, XP]
    def get_progress_text(user_name: str) -> str
    def adjust(user_name: str, delta: int, reason: str, source: str) -> XpAwardResult
    def handle_event(event: XpEvent) -> XpAwardResult | None
    def list_transactions(user_id: int, limit: int) -> list[XPTransaction]
```

### Database Schema

**xp** table:
```sql
CREATE TABLE xp (
    user_id INTEGER PRIMARY KEY,  -- 1:1 with users
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**xp_transactions** table:
```sql
CREATE TABLE xp_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,  -- Always positive for awards
    reason TEXT,  -- 'chat', 'tip', 'follow', etc.
    source TEXT,  -- 'joystick', 'admin', 'batch', etc.
    created_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Leveling Curve

### Formula

**Location**: `app/core/xp_curve.py`

XP required for level \( L \):

\[
\text{XP}_{required}(L) = \text{BASE} \times L^{\text{EXPONENT}}
\]

**Default Configuration**:
```ini
XP_BASE=100
XP_EXPONENT=1.8
XP_MAX_LEVEL=9999
```

### Example Progression

| Level | XP Required | Cumulative XP |
|-------|-------------|---------------|
| 1     | 0           | 0             |
| 2     | 100         | 100           |
| 3     | 344         | 444           |
| 4     | 724         | 1,168         |
| 5     | 1,179       | 2,347         |
| 10    | 6,310       | 29,194        |
| 20    | 46,697      | 443,584       |
| 50    | 706,786     | 16,900,583    |
| 100   | 3,981,072   | 198,012,826   |

### Calculation Code

```python
def xp_for_level(level: int, base: int = 100, exponent: float = 1.8) -> int:
    """XP required to reach this level from level 0."""
    if level <= 1:
        return 0
    
    total = 0
    for L in range(2, level + 1):
        total += int(base * (L ** exponent))
    return total

def level_from_xp(total_xp: int, base: int = 100, exponent: float = 1.8, max_level: int = 9999) -> int:
    """Determine level from total XP."""
    level = 1
    cumulative = 0
    
    while level < max_level:
        next_level_xp = int(base * ((level + 1) ** exponent))
        if cumulative + next_level_xp > total_xp:
            break
        cumulative += next_level_xp
        level += 1
    
    return level

def progress_to_next_level(total_xp: int, current_level: int, base: int = 100, exponent: float = 1.8) -> tuple[int, int, float]:
    """Returns (xp_into_current_level, xp_required_for_next, progress_ratio)."""
    xp_for_current = xp_for_level(current_level, base, exponent)
    xp_for_next = xp_for_level(current_level + 1, base, exponent)
    
    into = total_xp - xp_for_current
    required = xp_for_next - xp_for_current
    ratio = into / required if required > 0 else 1.0
    
    return (into, required, ratio)
```

## Earning XP

### Chat Messages

**Configuration**:
```ini
XP_CHAT_AMOUNT=1
XP_CHAT_COOLDOWN_SECONDS=30
```

**Behavior**: Similar to points, but separate cooldown

### Follows

**Configuration**:
```ini
XP_FOLLOW_AMOUNT=10
XP_FOLLOW_COOLDOWN_SECONDS=3600
```

### Drop-ins

**Configuration**:
```ini
XP_DROPIN_AMOUNT=5
XP_DROPIN_COOLDOWN_SECONDS=3600
```

### Subscriptions

**Configuration**:
```ini
XP_SUB_AMOUNT=50
XP_SUB_COOLDOWN_SECONDS=3600
```

**Multi-month**: XP is multiplied by number of months

```python
if event_type == "sub":
    months = event.metadata.get("months", 1)
    base_amount = settings.XP_SUB_AMOUNT  # 50
    award_amount = base_amount * months  # 50 * 3 = 150 for 3-month sub
```

### Tips

**Configuration**:
```ini
XP_TIP_PER_TOKEN=0.1
XP_TIP_COOLDOWN_SECONDS=30
```

**Example**:
```python
# User tips 100 tokens
xp_amount = int(100 * 0.1) = 10 XP
```

## Level-Up Rewards

**Location**: `app/core/level_rewards.py`

### Configuration File

**Path**: `./data/level_rewards.json`

```json
{
  "5": {
    "points": 500,
    "message": "Congrats on reaching level 5!"
  },
  "10": {
    "points": 1000,
    "message": "Level 10! You're on fire!",
    "tts": true
  },
  "25": {
    "points": 5000,
    "message": "Quarter century milestone!",
    "tts": true
  },
  "50": {
    "points": 10000,
    "message": "Halfway to 100!",
    "tts": true
  }
}
```

### Reward Types

#### 1. Bonus Points

```json
{
  "10": {"points": 1000}
}
```

User receives 1000 bonus points upon reaching level 10.

#### 2. Chat Messages

```json
{
  "15": {"message": "You hit level 15!"}
}
```

Bot sends congratulatory message to chat.

#### 3. TTS Announcements

```json
{
  "20": {
    "message": "Bob reached level 20!",
    "tts": true
  }
}
```

Message is queued for text-to-speech.

### Implementation

```python
def apply_level_rewards(
    db: Session,
    user_id: int,
    user_name: str,
    new_level: int,
    rewards_path: str = "./data/level_rewards.json"
) -> list[dict]:
    """
    Check if new_level has a reward defined.
    Apply rewards and return actions for caller to handle.
    """
    if not os.path.exists(rewards_path):
        return []
    
    with open(rewards_path) as f:
        rewards = json.load(f)
    
    reward = rewards.get(str(new_level))
    if not reward:
        return []
    
    actions = []
    
    # Grant bonus points
    if "points" in reward:
        points_service = PointsService(db)
        amount = int(reward["points"])
        points_service.grant(user_id, amount, reason=f"level_{new_level}")
        actions.append({"type": "points", "amount": amount})
    
    # Prepare message/TTS
    if "message" in reward:
        msg = reward["message"].replace("{user}", user_name).replace("{level}", str(new_level))
        
        if reward.get("tts"):
            actions.append({"type": "tts", "text": msg})
        else:
            actions.append({"type": "message", "text": msg})
    
    return actions
```

### Multiple Level-Ups

If a user gains enough XP to skip levels (e.g., large tip), rewards for each level are applied:

```python
if new_level > before_level:
    for lvl in range(before_level + 1, new_level + 1):
        reward_actions = apply_level_rewards(db, user_id, user_name, lvl, rewards_file)
        # Process each reward
```

**Example**:
```
User at level 4 receives 10,000 XP
Jumps to level 8
Rewards applied for: level 5, level 6, level 7, level 8
```

## Event Handling

### XpEvent Data Class

**Location**: `app/core/xp_policy.py`

```python
@dataclass
class XpEvent:
    type: str  # 'chat', 'follow', 'sub', 'tip', 'dropin'
    user: str
    source: str  # 'joystick', 'admin', etc.
    metadata: dict  # Additional data (tokens, months, etc.)
```

### Handling Flow

```python
async def on_tip(user: str, tokens: int):
    if not settings.XP_ENABLED:
        return
    
    event = XpEvent(
        type="tip",
        user=user,
        source="joystick",
        metadata={"tokens": tokens}
    )
    
    result = xp_service.handle_event(event)
    
    if result and result.ok:
        if result.level_after > result.level_before:
            # User leveled up!
            await send_message(f"@{user} leveled up to {result.level_after}!")
        
        # Process rewards
        for action in result.reward_actions:
            if action["type"] == "tts":
                # TTS already queued by service
                pass
            elif action["type"] == "message":
                await send_message(action["text"])
```

### XpAwardResult

```python
@dataclass
class XpAwardResult:
    ok: bool
    user_id: int
    user_name: str
    delta: int  # XP awarded
    total_xp: int  # New total
    level_before: int
    level_after: int
    reason: str
    source: str
    reward_actions: list[dict]  # Actions to execute
```

## Progress Tracking

### Progress Text

```python
text = xp_service.get_progress_text("alice")
# Returns: "@alice — Level 5 • XP 2500 • 153/1179 (13%)"
```

Breakdown:
- Current level: 5
- Total XP: 2500
- XP into current level: 153
- XP required for next level: 1179
- Progress percentage: 13%

### Progress Bar (Example)

```python
def progress_bar(current: int, required: int, width: int = 20) -> str:
    filled = int((current / required) * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"

into, required, ratio = progress_to_next_level(xp.total_xp, xp.level)
bar = progress_bar(into, required)
print(f"Level {xp.level} {bar} {into}/{required}")
# Output: "Level 5 [██░░░░░░░░░░░░░░░░░░] 153/1179"
```

## Admin Operations

### Manual XP Adjustment

```python
result = xp_service.adjust(
    user_name="alice",
    delta=1000,  # Can be positive or negative
    reason="admin_correction",
    source="admin"
)

print(f"New level: {result.level_after}")
```

**Note**: Negative delta can reduce XP and cause level-downs. Rewards are NOT reversed.

### Batch XP Operations

**See**: [Batch Operations Documentation](batch-operations.md)

```
POST /admin/api/users/batch-xp
{
  "operation": "add",
  "amount": 5000,
  "target": "all",
  "reason": "anniversary_event"
}
```

Response includes `level_ups` array showing who leveled:
```json
{
  "ok": true,
  "success": 10,
  "level_ups": [
    {"user_name": "alice", "level_before": 5, "level_after": 7},
    {"user_name": "bob", "level_before": 10, "level_after": 11}
  ]
}
```

## Configuration Reference

### Enable/Disable
```ini
XP_ENABLED=true
```

### Curve Parameters
```ini
XP_BASE=100
XP_EXPONENT=1.8
XP_MAX_LEVEL=9999
```

### Event Rewards
```ini
XP_CHAT_AMOUNT=1
XP_CHAT_COOLDOWN_SECONDS=30

XP_FOLLOW_AMOUNT=10
XP_FOLLOW_COOLDOWN_SECONDS=3600

XP_DROPIN_AMOUNT=5
XP_DROPIN_COOLDOWN_SECONDS=3600

XP_SUB_AMOUNT=50
XP_SUB_COOLDOWN_SECONDS=3600

XP_TIP_PER_TOKEN=0.1
XP_TIP_COOLDOWN_SECONDS=30
```

### Rewards File
```ini
XP_LEVEL_REWARDS_FILE=./data/level_rewards.json
```

## Tuning the Curve

### Linear Progression

```ini
XP_BASE=100
XP_EXPONENT=1.0
```

Every level requires 100 XP (too easy).

### Moderate Growth

```ini
XP_BASE=100
XP_EXPONENT=1.5
```

Slower growth than default (easier to level).

### Steep Growth (Default)

```ini
XP_BASE=100
XP_EXPONENT=1.8
```

Balanced for long-term engagement.

### Very Steep Growth

```ini
XP_BASE=100
XP_EXPONENT=2.5
```

Extremely difficult high levels (hardcore mode).

## Best Practices

### Curve Design

1. **Early levels**: Should be achievable quickly (1-10 in first stream)
2. **Mid levels**: Require consistent participation (10-50 over weeks)
3. **High levels**: Reserved for dedicated community members (50+ months/years)

### Reward Milestones

1. **Every 5 levels**: Small point bonus
2. **Every 10 levels**: Message + modest points
3. **Every 25 levels**: TTS announcement + large point bonus
4. **Round numbers** (10, 25, 50, 100): Special recognition

### XP vs Points

**XP**: Long-term achievement, never lost, prestige
**Points**: Short-term currency, spent on redeems, volatile

Users should earn both simultaneously but use them differently.

## Troubleshooting

### XP not being awarded

1. Check `XP_ENABLED=true`
2. Verify cooldowns aren't blocking awards
3. Check event type is configured (chat, tip, etc.)
4. Review logs for errors

### Incorrect levels

1. Verify `XP_BASE` and `XP_EXPONENT` values
2. Check `XP_MAX_LEVEL` hasn't been reached
3. Review XP transaction history
4. Recalculate: `level = level_from_xp(total_xp)`

### Rewards not triggering

1. Check `level_rewards.json` syntax
2. Verify file path in `XP_LEVEL_REWARDS_FILE`
3. Ensure level numbers are strings ("5", not 5)
4. Check logs for file read errors

## See Also

- [Points System](points-system.md) - Currency companion system
- [Event Flow](event-flow.md) - How XP events are processed
- [Database Schema](database-schema.md) - XP data model
- [Customization Guide](customization.md) - Custom reward types

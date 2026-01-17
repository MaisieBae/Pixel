# Redeems System

The Redeems System allows viewers to spend points on interactive features, triggering effects, sounds, messages, and other custom actions.

## Overview

Redeems are point-based purchases that viewers can make. Each redeem has:
- **Key**: Unique identifier (e.g., "tts", "spin", "clip")
- **Display Name**: User-friendly name shown in UI
- **Cost**: Points required to redeem
- **Enabled**: Whether the redeem is currently active
- **Cooldown**: Seconds before user can redeem again

## Architecture

### Service Class: `RedeemsService`

**Location**: `app/core/redeems.py`

```python
class RedeemsService:
    def seed_defaults(settings: Settings | None) -> None
    def get(key: str) -> Redeem | None
    def list() -> list[Redeem]
    def toggle(key: str, enabled: bool) -> None
    def upsert(key: str, display_name: str, cost: int, enabled: bool, cooldown_s: int) -> Redeem
    def redeem(user_name: str, key: str, cooldown_s: int | None, queue_kind: str | None, payload: dict | None) -> dict
```

### Database Schema

**redeems** table:
```sql
CREATE TABLE redeems (
    key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    cost INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    cooldown_s INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Default Redeems

### 1. Text-to-Speech (TTS)

**Key**: `tts`
**Default Cost**: 25 points
**Cooldown**: 10 seconds (configurable via `TTS_COOLDOWN_SECONDS`)

**Usage**: User spends points to have a message read aloud

**Flow**:
```python
1. User triggers TTS redeem with message
2. Check if TTS enabled and user has points
3. Check cooldown
4. Spend points (25)
5. Queue TTS item with message
6. Set cooldown
7. TTS processor plays pre-sound
8. TTS engine speaks message
9. Mark queue item complete
```

**Configuration**:
```ini
TTS_COOLDOWN_SECONDS=10
TTS_QUEUE_MAX=5
TTS_PRE_SOUND=announcement.wav
TTS_PREFIX_USERNAME=true
```

### 2. Pixel Reply

**Key**: `pixel`
**Default Cost**: 50 points
**Cooldown**: 20 seconds

**Usage**: User asks Pixel (AI assistant) a question

**Flow**:
```python
1. User triggers pixel redeem with question
2. Check points and cooldown
3. Spend points (50)
4. Call Perplexity API with question
5. Get AI response (limited to 2 sentences)
6. Send response to chat
7. Set cooldown
```

**See**: [AI Chat Documentation](ai-chat.md)

### 3. Play Sound

**Key**: `sound`
**Default Cost**: 15 points
**Cooldown**: 5 seconds

**Usage**: Play a sound effect from the sounds directory

**Flow**:
```python
1. User triggers sound redeem (optionally with sound name)
2. Check points and cooldown
3. Spend points (15)
4. Look up sound file in sounds/ directory
5. Play sound via overlay bus
6. Set cooldown
```

### 4. Prize Wheel Spin

**Key**: `spin`
**Default Cost**: 100 points
**Cooldown**: None (limited by queue)

**Usage**: Spin the prize wheel for random reward

**Flow**:
```python
1. User triggers spin redeem
2. Check points
3. Spend points (100)
4. Queue wheel spin
5. Wheel processor:
   - Plays spin sound effects
   - Animates wheel
   - Selects prize (weighted random)
   - Awards prize (points, items, effects)
   - Announces winner
6. Complete
```

**See**: [Prize Wheel Documentation](prize-wheel.md)

### 5. Save Clip

**Key**: `clip`
**Default Cost**: 0 points (free)
**Cooldown**: 5 seconds

**Usage**: Trigger OBS to save a clip of the stream

**Flow**:
```python
1. User triggers clip redeem
2. Check cooldown (prevents spam)
3. Send command to OBS WebSocket
4. OBS saves replay buffer
5. Set cooldown
```

**Requirements**: OBS WebSocket enabled and configured

## Redeem Flow

### Standard Redeem Process

```python
result = redeems_service.redeem(
    user_name="alice",
    key="tts",
    cooldown_s=None,  # Use DB value
    queue_kind="tts",
    payload={
        "user": "alice",
        "message": "Hello world",
        "prefix": True,
        "source": "redeem"
    }
)

if result["ok"]:
    print(f"Queued: {result['queue_id']}")
else:
    print(f"Failed: {result['error']}")
```

### Response Format

**Success**:
```json
{
  "ok": true,
  "user": "alice",
  "redeem": "tts",
  "queue_id": 42
}
```

**Failure - Insufficient Points**:
```json
{
  "ok": false,
  "error": "Insufficient points"
}
```

**Failure - Cooldown**:
```json
{
  "ok": false,
  "error": "Cooldown active: 7s left"
}
```

**Failure - Disabled**:
```json
{
  "ok": false,
  "error": "Redeem disabled or missing"
}
```

## Custom Redeems

### Creating a New Redeem

**Step 1: Define in Database**

```python
redeems_service.upsert(
    key="custom_effect",
    display_name="Custom Effect",
    cost=250,
    enabled=True,
    cooldown_s=30
)
```

**Step 2: Create Handler**

Add to your event consumers or create a new handler:

```python
# In consumers.py or custom module
async def handle_custom_effect(user: str, payload: dict):
    with SessionLocal() as db:
        redeems = RedeemsService(db)
        
        result = redeems.redeem(
            user_name=user,
            key="custom_effect",
            cooldown_s=None,
            queue_kind="effect",
            payload={
                "user": user,
                "effect_type": "rainbow",
                "duration": 10
            }
        )
        
        if result["ok"]:
            # Queue item created, processor will handle it
            await send_message(f"@{user} triggered custom effect!")
        else:
            await send_message(f"@{user} {result['error']}")
```

**Step 3: Process Queue Item**

```python
# In your queue processor
async def process_effect_queue(item: QueueItem):
    payload = item.payload_json
    effect_type = payload.get("effect_type")
    
    if effect_type == "rainbow":
        await trigger_rainbow_lights()
        await asyncio.sleep(payload.get("duration", 5))
    
    # Mark complete
    item.status = "done"
    item.finished_at = datetime.utcnow()
    db.commit()
```

### Advanced: Conditional Redeems

Redeems that behave differently based on conditions:

```python
async def handle_mystery_redeem(user: str):
    with SessionLocal() as db:
        redeems = RedeemsService(db)
        points_svc = PointsService(db)
        
        result = redeems.redeem(
            user_name=user,
            key="mystery",
            cooldown_s=None,
            queue_kind=None,  # No queue, handle immediately
            payload={"user": user}
        )
        
        if not result["ok"]:
            await send_message(f"@{user} {result['error']}")
            return
        
        # Mystery logic: random reward
        u = points_svc.ensure_user(user)
        reward = random.choice([
            ("points", 500),
            ("points", 1000),
            ("xp", 100),
            ("nothing", 0)
        ])
        
        if reward[0] == "points":
            points_svc.grant(u.id, reward[1], "mystery_reward")
            await send_message(f"@{user} won {reward[1]} points!")
        elif reward[0] == "xp":
            xp_svc.adjust(user, reward[1], reason="mystery_reward", source="redeem")
            await send_message(f"@{user} won {reward[1]} XP!")
        else:
            await send_message(f"@{user} won... nothing! Better luck next time!")
```

## Admin Management

### Via Admin Dashboard

1. Navigate to `/admin`
2. Go to "Redeems" tab (if implemented)
3. Edit redeem properties:
   - Display name
   - Cost
   - Enabled/disabled
   - Cooldown duration

### Via API

**List Redeems**:
```
GET /admin/api/redeems
```

Response:
```json
[
  {
    "key": "tts",
    "display_name": "Text-to-Speech",
    "cost": 25,
    "enabled": true,
    "cooldown_s": 10
  },
  ...
]
```

**Toggle Redeem**:
```
POST /admin/api/redeems/tts/toggle
{
  "enabled": false
}
```

**Update Redeem**:
```
POST /admin/api/redeems/tts
{
  "display_name": "Speak Message",
  "cost": 50,
  "enabled": true,
  "cooldown_s": 15
}
```

## Cooldown Mechanics

### Per-User Cooldowns

Cooldowns are tracked per user, per redeem:

```python
# Alice redeems TTS at 12:00:00
# Cooldown set: 10 seconds
# Alice cannot redeem TTS again until 12:00:10
# Bob can still redeem TTS (independent cooldown)
```

### Override Cooldown

You can override the database cooldown for special cases:

```python
result = redeems.redeem(
    user_name="alice",
    key="tts",
    cooldown_s=0,  # No cooldown for this redemption
    queue_kind="tts",
    payload={...}
)
```

### Global vs Per-User

Current implementation uses per-user cooldowns. To implement global cooldowns:

```python
class RedeemsService:
    def redeem_global(self, user_name: str, key: str, ...):
        # Check global cooldown using a sentinel user_id (e.g., 0)
        active, _ = self.cooldowns.is_active(0, f"global:{key}")
        if active:
            return {"ok": False, "error": "Global cooldown active"}
        
        # ... normal redeem logic ...
        
        # Set global cooldown
        self.cooldowns.set(0, f"global:{key}", cooldown_s)
```

## Queue Integration

### Queue-Based Redeems

Some redeems (TTS, wheel, effects) use the queue system:

```python
queue_id = redeems.redeem(
    user_name="alice",
    key="tts",
    queue_kind="tts",
    payload={"message": "Hello"}
)["queue_id"]

# Later, queue processor handles it
item = db.get(QueueItem, queue_id)
if item and item.status == "pending":
    await process_tts(item)
```

**Benefits**:
- Sequential processing (TTS messages don't overlap)
- Fair ordering (first-come, first-served)
- Retry capability
- Status tracking

### Immediate Redeems

Some redeems don't need queueing:

```python
result = redeems.redeem(
    user_name="alice",
    key="clip",
    queue_kind=None,  # No queue
    payload=None
)

# Handle immediately
if result["ok"]:
    await obs_client.trigger_clip()
```

## Testing Redeems

### Manual Testing

```python
# In Python console or test script
from app.core.db import SessionLocal
from app.core.redeems import RedeemsService

with SessionLocal() as db:
    redeems = RedeemsService(db)
    
    # Test TTS redeem
    result = redeems.redeem(
        user_name="testuser",
        key="tts",
        cooldown_s=0,  # Disable cooldown for testing
        queue_kind="tts",
        payload={"user": "testuser", "message": "Test message"}
    )
    
    print(result)
```

### Cooldown Testing

```python
import time

# First redemption
result1 = redeems.redeem("testuser", "tts", ...)
assert result1["ok"] == True

# Immediate retry (should fail)
result2 = redeems.redeem("testuser", "tts", ...)
assert result2["ok"] == False
assert "Cooldown" in result2["error"]

# Wait for cooldown
time.sleep(11)

# Should succeed now
result3 = redeems.redeem("testuser", "tts", ...)
assert result3["ok"] == True
```

## Best Practices

### Pricing Redeems

1. **Free/Low Cost** (0-50 points):
   - Clips
   - Simple sounds
   - Common effects

2. **Medium Cost** (50-200 points):
   - TTS messages
   - AI responses
   - Music requests

3. **High Cost** (200-1000 points):
   - Prize wheel spins
   - Major effects
   - Special privileges

4. **Premium** (1000+ points):
   - Game choices
   - Stream decisions
   - Exclusive content

### Setting Cooldowns

1. **No Cooldown**:
   - Clips (rate-limited by OBS)
   - One-time purchases

2. **Short Cooldown** (5-15s):
   - Sound effects
   - Simple visual effects

3. **Medium Cooldown** (30-60s):
   - TTS messages
   - Complex effects

4. **Long Cooldown** (5-30 minutes):
   - Major stream impacts
   - Resource-intensive operations

### Disabling Problematic Redeems

Quickly disable a redeem without deleting:

```python
redeems.toggle("tts", enabled=False)
```

Re-enable when ready:

```python
redeems.toggle("tts", enabled=True)
```

## Troubleshooting

### Redeem not working

1. Check if enabled: `redeems.get("tts").enabled`
2. Verify user has points
3. Check cooldown status
4. Review queue for stuck items
5. Check logs for errors

### Points deducted but effect didn't happen

1. Check queue status: `db.get(QueueItem, queue_id)`
2. Look for `status="failed"`
3. Review error in queue item
4. Manually refund if needed:
   ```python
   points.grant(user_id, cost, reason="refund:failed_redeem")
   ```

### Cooldown too long/short

1. Update via admin dashboard or:
   ```python
   redeem = redeems.get("tts")
   redeem.cooldown_s = 30  # New cooldown
   db.commit()
   ```

### Queue backlog

If queue gets backed up:

```python
# Clear failed items
failed = db.scalars(
    select(QueueItem).where(
        QueueItem.kind == "tts",
        QueueItem.status == "failed"
    )
)
for item in failed:
    db.delete(item)
db.commit()

# Or mark all pending as complete (use carefully!)
pending = db.scalars(
    select(QueueItem).where(
        QueueItem.kind == "tts",
        QueueItem.status == "pending"
    )
)
for item in pending:
    item.status = "done"
db.commit()
```

## See Also

- [TTS System](tts.md) - Text-to-speech details
- [Prize Wheel](prize-wheel.md) - Wheel mechanics
- [AI Chat](ai-chat.md) - Pixel reply system
- [Points System](points-system.md) - Point economics
- [Queue System](event-flow.md#queue-processing) - Queue mechanics

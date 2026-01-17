# Redeems System

The Redeems System allows users to spend points on interactive effects and features. It provides a flexible framework for creating custom channel point redeems with cost management, cooldowns, and effect triggering.

## Overview

Redeems are point-based purchases that trigger various effects:
- Text-to-Speech messages
- AI-powered bot replies
- Sound effects
- Prize wheel spins
- OBS clips
- Custom effects

Each redeem has:
- **Key**: Unique identifier
- **Display Name**: User-friendly name
- **Cost**: Point price
- **Enabled**: Can be toggled on/off
- **Cooldown**: Seconds before user can redeem again

## Architecture

### Service Class: `RedeemsService`

**Location**: `app/core/redeems.py`

```python
class RedeemsService:
    def seed_defaults(settings: Settings) -> None
    def get(key: str) -> Redeem | None
    def list() -> list[Redeem]
    def toggle(key: str, enabled: bool) -> None
    def upsert(key: str, display_name: str, cost: int, enabled: bool, cooldown_s: int) -> Redeem
    def redeem(user_name: str, key: str, cooldown_s: int, queue_kind: str, payload: dict) -> dict
```

### Database Schema

**redeems** table:
```sql
CREATE TABLE redeems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
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
**Default Cooldown**: 10 seconds  

**Usage**:
```
!tts Hello everyone!
```

**Flow**:
1. User types `!tts` command with message
2. Bot checks if TTS redeem is enabled
3. Validates point balance (>= 25)
4. Checks user cooldown (10s)
5. Spends 25 points
6. Queues TTS with message
7. Sets cooldown
8. TTS processor picks up queue item
9. Plays pre-sound announcement
10. Speaks message with optional username prefix

### 2. Pixel Reply (AI Chat)

**Key**: `pixel`  
**Default Cost**: 50 points  
**Default Cooldown**: 20 seconds  

**Usage**:
```
!pixel What's the weather like?
```

**Flow**:
1. User asks question to Pixel
2. Spends 50 points
3. Query sent to Perplexity AI
4. Bot replies in chat with answer
5. Cooldown set

### 3. Play Sound

**Key**: `sound`  
**Default Cost**: 15 points  
**Default Cooldown**: 5 seconds  

**Usage**:
```
!sound airhorn
```

**Flow**:
1. User requests sound effect
2. Spends 15 points
3. Sound file played through overlay
4. Sets cooldown

### 4. Prize Wheel Spin

**Key**: `spin`  
**Default Cost**: 100 points  
**Default Cooldown**: 0 seconds (no limit)  

**Usage**:
```
!spin
```

**Flow**:
1. User requests wheel spin
2. Spends 100 points
3. Queues wheel spin effect
4. Wheel spins with animation and sound
5. Prize determined by weighted random
6. Prize awarded (points, XP, item, etc.)
7. Result announced

### 5. Save Clip

**Key**: `clip`  
**Default Cost**: 0 points (free)  
**Default Cooldown**: 5 seconds  

**Usage**:
```
!clip
```

**Flow**:
1. User requests clip
2. Bot triggers OBS WebSocket
3. OBS saves replay buffer
4. Confirmation sent to chat

## Redeem Flow

### Core Redeem Process

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
    print(f"Redeemed! Queue ID: {result['queue_id']}")
else:
    print(f"Failed: {result['error']}")
```

### Validation Steps

1. **Enabled Check**
   ```python
   if not redeem.enabled:
       return {"ok": False, "error": "Redeem disabled"}
   ```

2. **Cooldown Check**
   ```python
   active, remaining = cooldowns.is_active(user_id, redeem_key)
   if active:
       return {"ok": False, "error": f"Cooldown: {remaining}s"}
   ```

3. **Point Check & Spend**
   ```python
   try:
       points.spend(user_id, redeem.cost, reason=f"redeem:{key}")
   except ValueError:
       return {"ok": False, "error": "Insufficient points"}
   ```

4. **Set Cooldown**
   ```python
   if cooldown_s > 0:
       cooldowns.set(user_id, redeem_key, cooldown_s)
   ```

5. **Queue Effect**
   ```python
   if queue_kind:
       queue_id = queue.enqueue(queue_kind, payload)
   ```

### Response Format

**Success**:
```python
{
    "ok": True,
    "user": "alice",
    "redeem": "tts",
    "queue_id": 42
}
```

**Failure**:
```python
{
    "ok": False,
    "error": "Insufficient points"  # or "Cooldown active", "Redeem disabled"
}
```

## Queue Integration

Many redeems use the queue system for sequential processing:

### Queue Kinds

- `tts` - Text-to-speech requests
- `pixel` - AI chat responses
- `sound` - Sound effect playback
- `spin` - Wheel spins
- `effect` - Custom effects

### Queue Item Structure

```python
QueueItem(
    kind="tts",
    status="pending",  # pending → running → done/failed
    payload_json={
        "user": "alice",
        "message": "Hello!",
        "prefix": True,
        "source": "redeem"
    },
    created_at=datetime.utcnow()
)
```

### Queue Processing

Queue items are processed sequentially:

1. Processor queries for oldest `pending` item of given `kind`
2. Changes status to `running`
3. Executes effect (plays TTS, spins wheel, etc.)
4. Changes status to `done` or `failed`
5. Moves to next item

## Creating Custom Redeems

### Step 1: Define Redeem

```python
# In consumers.py or custom handler
async def handle_custom_redeem(user: str, args: list[str]):
    with SessionLocal() as db:
        redeems = RedeemsService(db)
        
        result = redeems.redeem(
            user_name=user,
            key="my_custom_redeem",
            queue_kind="effect",
            payload={
                "user": user,
                "effect_type": "confetti",
                "duration": 5
            }
        )
        
        if not result["ok"]:
            await send_message(f"@{user} {result['error']}")
            return
        
        await send_message(f"@{user} activated confetti!")
```

### Step 2: Register in Database

```python
redeems.upsert(
    key="my_custom_redeem",
    display_name="Confetti Blast",
    cost=75,
    enabled=True,
    cooldown_s=30
)
```

### Step 3: Create Effect Handler

```python
# In effects/ directory
async def process_confetti_effect(payload: dict):
    user = payload.get("user")
    duration = payload.get("duration", 5)
    
    # Trigger visual effect
    await overlay_bus.send({
        "type": "confetti",
        "duration": duration
    })
    
    # Play sound
    await play_sfx("party_horn.wav")
    
    # Send chat message
    await send_message(f"🎉 {user} triggered confetti! 🎉")
```

### Step 4: Wire Up Queue Processor

```python
# In queue processor loop
if item.kind == "effect":
    payload = item.payload_json or {}
    effect_type = payload.get("effect_type")
    
    if effect_type == "confetti":
        await process_confetti_effect(payload)
    elif effect_type == "fireworks":
        await process_fireworks_effect(payload)
    # ... etc
```

## Admin Management

### Via Dashboard

1. Navigate to `/admin`
2. Click "Redeems" tab
3. View list of all redeems
4. Toggle enabled/disabled
5. Edit cost, cooldown, display name
6. Create new custom redeems

### Via API

**List Redeems**:
```
GET /admin/api/redeems
```

**Response**:
```json
[
  {
    "key": "tts",
    "display_name": "Text-to-Speech",
    "cost": 25,
    "enabled": true,
    "cooldown_s": 10
  },
  {
    "key": "pixel",
    "display_name": "Pixel Reply",
    "cost": 50,
    "enabled": true,
    "cooldown_s": 20
  }
]
```

**Toggle Redeem**:
```
POST /admin/api/redeems/{key}/toggle
{"enabled": false}
```

**Update Redeem**:
```
PUT /admin/api/redeems/{key}
{
  "display_name": "Speak Text",
  "cost": 30,
  "cooldown_s": 15
}
```

## Configuration

### TTS Settings

```ini
TTS_QUEUE_MAX=5
TTS_COOLDOWN_SECONDS=10
TTS_PREFIX_USERNAME=true
TTS_PRE_SOUND=announcement.wav
TTS_PRE_DELAY_MS=1200
```

### Pixel (AI) Settings

```ini
PPLX_API_KEY=your-api-key
PPLX_MODEL=sonar-small-online
PPLX_MAX_TOKENS=200
PPLX_TIMEOUT=12
PIXEL_MAX_CHARS=220
PIXEL_MAX_SENTENCES=2
```

### Wheel Settings

```ini
PRIZES_FILE=./data/prizes.json
WHEEL_SPIN_MIN=2
WHEEL_SPIN_MAX=10
WHEEL_SFX_START=wheel_start.wav
WHEEL_SFX_LOOP=wheel_loop.wav
WHEEL_SFX_WIN=wheel_win.wav
```

## Cooldown Management

### Per-User Cooldowns

Cooldowns are tracked per user per redeem:

```python
# User A redeems TTS → 10s cooldown for User A
# User B can still redeem TTS immediately
# User A must wait 10s before next TTS
```

### Global vs Per-User

By default, cooldowns are **per-user**. To implement global cooldowns:

```python
# Check global cooldown (special user_id = 0)
active, remaining = cooldowns.is_active(0, redeem_key)
if active:
    return {"ok": False, "error": "Redeem on global cooldown"}

# Set global cooldown
cooldowns.set(0, redeem_key, 60)
```

### Cooldown Override

Admins can bypass cooldowns:

```python
# Don't check cooldown for admins
if user.is_admin:
    cooldown_s = 0  # No cooldown
```

## Best Practices

### Pricing Strategy

1. **Free/Low Cost** (0-25 pts): Simple effects, clips
2. **Medium Cost** (25-100 pts): TTS, sounds, basic effects
3. **High Cost** (100-500 pts): AI replies, wheel spins, premium effects
4. **Very High Cost** (500+ pts): Rare/powerful effects

### Cooldown Timing

1. **Frequent Use** (5-15s): Sounds, clips
2. **Moderate Use** (15-60s): TTS, effects
3. **Limited Use** (60-300s): AI replies, expensive effects
4. **Rare Use** (300+ s): Game-changing effects

### Effect Design

1. **Visual Feedback**: Always show something happened
2. **Audio Cues**: Confirm redemption with sound
3. **Chat Confirmation**: Send message acknowledging redeem
4. **Time Limits**: Don't make effects too long (5-15s max)

## Troubleshooting

### Redeem not working

1. Check if redeem is enabled: `redeems.get(key).enabled`
2. Verify user has enough points
3. Check cooldown status
4. Review queue for stuck items
5. Check logs for errors

### Cooldown not resetting

1. Cooldowns are in-memory (reset on bot restart)
2. Verify cooldown_s value in database
3. Check system time is correct
4. Clear specific cooldown: `cooldowns.clear(user_id, key)`

### Queue backing up

1. Check queue processor is running
2. Look for failed items blocking queue
3. Manually mark stuck items as `failed`
4. Increase `TTS_QUEUE_MAX` if needed

### Points not being spent

1. Verify `redeem()` returns `ok: true`
2. Check transaction log for spend record
3. Ensure error handling doesn't skip spend
4. Review point balance before/after

## Example: Complete Custom Redeem

Here's a full example of a custom "Highlight Clip" redeem:

```python
# 1. Define redeem in database
with SessionLocal() as db:
    redeems = RedeemsService(db)
    redeems.upsert(
        key="highlight",
        display_name="Create Highlight",
        cost=150,
        enabled=True,
        cooldown_s=120  # 2 minutes
    )

# 2. Create command handler
async def handle_highlight_command(user: str, args: list[str]):
    with SessionLocal() as db:
        redeems = RedeemsService(db)
        
        # Custom: allow user to specify duration
        duration = 30  # default
        if args:
            try:
                duration = max(10, min(60, int(args[0])))
            except ValueError:
                pass
        
        result = redeems.redeem(
            user_name=user,
            key="highlight",
            queue_kind="clip",
            payload={
                "user": user,
                "duration": duration,
                "type": "highlight"
            }
        )
        
        if not result["ok"]:
            await joystick.send_message(f"@{user} {result['error']}")
            return
        
        await joystick.send_message(
            f"@{user} highlight clip queued ({duration}s)!"
        )

# 3. Register command
commands["!highlight"] = handle_highlight_command

# 4. Process queue item
async def process_clip_queue():
    while True:
        with SessionLocal() as db:
            item = db.scalar(
                select(QueueItem)
                .where(QueueItem.kind == "clip", QueueItem.status == "pending")
                .order_by(QueueItem.id.asc())
                .limit(1)
            )
            
            if not item:
                await asyncio.sleep(1)
                continue
            
            item.status = "running"
            db.commit()
            
            payload = item.payload_json or {}
            duration = payload.get("duration", 30)
            
            try:
                # Trigger OBS
                await obs.save_replay_buffer()
                
                # Success
                item.status = "done"
                item.finished_at = datetime.utcnow()
                await joystick.send_message(
                    f"✅ Clip saved! ({duration}s)"
                )
            except Exception as e:
                # Failure
                item.status = "failed"
                item.finished_at = datetime.utcnow()
                await joystick.send_message(
                    f"❌ Clip failed: {e}"
                )
            
            db.commit()

# 5. Start processor
asyncio.create_task(process_clip_queue())
```

## See Also

- [Points System](points-system.md) - Currency for redeems
- [TTS](tts.md) - Text-to-speech details
- [Prize Wheel](prize-wheel.md) - Wheel spin mechanics
- [AI Chat](ai-chat.md) - Pixel reply system
- [Event Flow](event-flow.md) - How redeems are processed

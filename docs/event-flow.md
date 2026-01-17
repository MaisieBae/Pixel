# Event Flow

This document explains how events flow through Pixel Bot from external sources to final actions.

## Event Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    External Event Source                    │
│              (Joystick.tv, Admin API, etc.)                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     1. Event Capture                        │
│                                                             │
│  • JoystickClient WebSocket                                 │
│  • Admin API endpoints                                      │
│  • Browser extension triggers                               │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  2. Event Normalization                     │
│                                                             │
│  • Parse payload                                            │
│  • Extract user, amount, metadata                           │
│  • Classify event type (chat, tip, follow, etc.)            │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. Event Dispatch                        │
│                                                             │
│  • Route to appropriate consumer                            │
│  • on_chat(), on_tip(), on_follow(), etc.                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   4. Cooldown Check                         │
│                                                             │
│  • Check if user is on cooldown for this event type         │
│  • If active, skip processing                               │
│  • If expired, continue                                     │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   5. Reward Processing                      │
│                                                             │
│  • Calculate points/XP amounts                              │
│  • Call PointsService.grant()                               │
│  • Call XpService.handle_event()                            │
│  • Update database (transactions)                           │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   6. Level-Up Detection                     │
│                                                             │
│  • Check if XP caused level change                          │
│  • Apply level rewards (points, messages)                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    7. Side Effects                          │
│                                                             │
│  • Queue TTS messages                                       │
│  • Trigger sound effects                                    │
│  • Send chat responses                                      │
│  • Update OBS scenes                                        │
│  • Notify overlay                                           │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  8. Cooldown Update                         │
│                                                             │
│  • Set new cooldown timer                                   │
│  • Prevent duplicate processing                             │
└─────────────────────────────────────────────────────────────┘
```

## Event Types

### 1. Chat Message

**Source**: Joystick.tv ChatMessage event

**Payload**:
```json
{
  "event": "ChatMessage",
  "text": "hello world",
  "author": {
    "username": "alice",
    "displayName": "Alice"
  },
  "channelId": "abc123"
}
```

**Flow**:
```python
1. JoystickClient receives ChatMessage
2. Parses user="alice", text="hello world"
3. Calls on_chat("alice", "hello world")
4. Consumer checks POINTS_ENABLED and XP_ENABLED
5. Checks cooldown for "points:chat" and "xp:chat"
6. If not on cooldown:
   - Grant 1 point (reason="chat")
   - Award 1 XP (reason="chat")
   - Set cooldowns (60s for points, 30s for XP)
7. Check if chat triggers AI response (random probability)
8. If yes, query Perplexity API and send reply
```

### 2. Follow

**Source**: Joystick.tv StreamEvent (Followed)

**Payload**:
```json
{
  "event": "StreamEvent",
  "type": "Followed",
  "metadata": "{\"who\":\"bob\"}"
}
```

**Flow**:
```python
1. JoystickClient receives StreamEvent
2. Detects type="Followed"
3. Parses metadata.who="bob"
4. Calls on_follow("bob")
5. Consumer ensures user exists
6. Grants 50 points (reason="follow")
7. Awards 10 XP (reason="follow")
8. Sends thank you message to chat
```

### 3. Subscription

**Source**: Joystick.tv StreamEvent (Subscribed)

**Payload**:
```json
{
  "event": "StreamEvent",
  "type": "Subscribed",
  "metadata": "{\"who\":\"charlie\",\"months\":3}"
}
```

**Flow**:
```python
1. JoystickClient receives StreamEvent
2. Detects type="Subscribed"
3. Parses metadata: who="charlie", months=3
4. Calls on_sub("charlie", 3)
5. Consumer calculates rewards:
   - Points: 200 * 3 = 600
   - XP: 50 * 3 = 150
6. Grants 600 points (reason="sub")
7. Awards 150 XP (reason="sub")
8. XP triggers level-up (5 → 7)
9. Level rewards applied:
   - Level 6: +1000 points
   - Level 7: +1500 points, TTS announcement
10. TTS queued: "Charlie reached level 7!"
11. Send thank you message to chat
```

### 4. Tip

**Source**: Joystick.tv StreamEvent (Tipped) or Browser Extension

**Payload**:
```json
{
  "event": "StreamEvent",
  "type": "Tipped",
  "metadata": "{\"who\":\"dave\",\"how_much\":250}"
}
```

**Flow**:
```python
1. JoystickClient receives StreamEvent
2. Detects type="Tipped"
3. Parses metadata: who="dave", tokens=250
4. Calls on_tip("dave", 250)
5. Consumer checks cooldowns
6. Calculates rewards:
   - Points: 250 * 1.0 = 250
   - XP: 250 * 0.1 = 25
7. Grants 250 points (reason="tip")
8. Awards 25 XP (reason="tip")
9. Determines tip tier: 250 = HIGH (100-500)
10. Plays corresponding sound effect
11. Triggers OBS clip creation (if enabled)
12. Sends thank you message with tier emoji
13. Sets cooldowns (30s)
```

### 5. Drop-in (User Enters Stream)

**Source**: Joystick.tv UserPresence event

**Payload**:
```json
{
  "event": "UserPresence",
  "type": "enter_stream",
  "text": "eve"
}
```

**Flow**:
```python
1. JoystickClient receives UserPresence
2. Detects type="enter_stream"
3. Extracts user="eve"
4. Calls on_dropin("eve")
5. Consumer checks cooldown (3600s = once per stream)
6. If not on cooldown:
   - Grant 25 points (reason="dropin")
   - Award 5 XP (reason="dropin")
   - Set cooldown (1 hour)
7. Optional: Send welcome message
```

### 6. Channel Point Redeem

**Source**: Joystick.tv RewardRedemption event (or custom implementation)

**Payload**:
```json
{
  "event": "RewardRedemption",
  "reward_id": "wheel_spin",
  "user": "frank",
  "user_input": ""
}
```

**Flow**:
```python
1. JoystickClient receives RewardRedemption
2. Extracts reward_id="wheel_spin"
3. Looks up handler in redeem_handlers dict
4. Calls handle_wheel_spin({"user": "frank"})
5. Handler checks point balance
6. If sufficient:
   - Spend 500 points (reason="wheel_spin")
   - Queue wheel spin effect
   - Spin wheel and determine prize
   - Award prize (points, XP, or custom)
   - Play sound effects
   - Send result message
7. If insufficient:
   - Send error message: "Need 500 points!"
```

## Event Processing Details

### Cooldown System

**Purpose**: Prevent spam and excessive database writes

**Implementation**:
```python
class CooldownService:
    def __init__(self, db: Session):
        self._cooldowns: dict[tuple[int, str], float] = {}
    
    def is_active(self, user_id: int, key: str) -> tuple[bool, int]:
        entry = (user_id, key)
        if entry not in self._cooldowns:
            return False, 0
        
        expires_at = self._cooldowns[entry]
        now = time.time()
        
        if now >= expires_at:
            del self._cooldowns[entry]
            return False, 0
        
        remaining = int(expires_at - now)
        return True, remaining
    
    def set(self, user_id: int, key: str, duration_seconds: int):
        entry = (user_id, key)
        self._cooldowns[entry] = time.time() + duration_seconds
```

**Cooldown Keys**:
- `points:chat` - Chat point cooldown
- `xp:chat` - Chat XP cooldown
- `points:tip` - Tip point cooldown
- `xp:tip` - Tip XP cooldown
- `points:follow` - Follow cooldown
- `xp:follow` - Follow XP cooldown
- `points:dropin` - Drop-in cooldown
- `xp:dropin` - Drop-in XP cooldown
- `redeem:{id}` - Per-redeem cooldowns
- `tts:user` - TTS usage cooldown

**Note**: Cooldowns are in-memory only (reset on bot restart).

### Transaction Logging

Every point and XP change is logged:

```python
# Points transaction
tx = Transaction(
    user_id=5,
    type="grant",  # or "spend", "adjust"
    delta=100,
    reason="tip",
    created_at=datetime.utcnow()
)
db.add(tx)
db.commit()

# XP transaction
xp_tx = XPTransaction(
    user_id=5,
    delta=10,
    reason="tip",
    source="joystick",
    created_at=datetime.utcnow()
)
db.add(xp_tx)
db.commit()
```

**Benefits**:
- Full audit trail
- Debugging incorrect balances
- Analytics and reporting
- Rollback capability (manual)

### Queue Processing

Some effects are queued for sequential processing:

```python
# Queue TTS
item = QueueItem(
    kind="tts",
    status="pending",
    payload_json={
        "user": "alice",
        "message": "Hello world",
        "prefix": True,
        "source": "redeem"
    },
    created_at=datetime.utcnow()
)
db.add(item)
db.commit()

# Queue processor picks up "pending" items
# Processes one at a time
# Marks as "processing" then "complete" or "failed"
```

**Queue Types**:
- `tts` - Text-to-speech requests
- `wheel` - Prize wheel spins
- `effect` - Custom effects

## Parallel vs Sequential Processing

### Parallel (Concurrent)

✓ Point and XP awards (independent systems)
✓ Multiple event consumers (chat + tips simultaneously)
✓ Admin API operations

### Sequential (Queued)

✓ TTS messages (one at a time for clarity)
✓ Wheel spins (visual effect constraint)
✓ OBS scene changes (prevent race conditions)

## Error Handling

### Database Errors

```python
try:
    points_service.grant(user_id, amount, reason)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    await send_message("Sorry, something went wrong!")
    # Don't set cooldown if award failed
    return
```

### External Service Failures

```python
# OBS WebSocket unavailable
try:
    obs_client.trigger_clip()
except ConnectionError:
    logger.warning("OBS not available, skipping clip")
    # Continue processing other effects
```

### Validation Errors

```python
# Insufficient points
try:
    points_service.spend(user_id, cost, reason)
except ValueError as e:
    await send_message(f"@{user} {str(e)}")
    return
```

## Performance Optimizations

### Batch Database Operations

When processing multiple events:

```python
# BAD: Multiple commits
for user in users:
    points.grant(user.id, 100, "event")
    # Each grant() commits

# GOOD: Batch commit
with SessionLocal() as db:
    for user in users:
        pts = db.get(Points, user.id)
        pts.balance += 100
        db.add(Transaction(...))
    db.commit()  # Single commit at end
```

### Cooldown Caching

Cooldowns are in-memory (not database) for speed:
- No database query needed to check cooldown
- No database write to set cooldown
- Trade-off: Lost on restart (acceptable)

### Event Deduplication

Joystick may send duplicate events. Deduplication strategies:

1. **Event IDs**: Track processed event IDs
2. **Cooldowns**: Natural dedup (can't process twice within cooldown)
3. **Transaction timestamps**: Detect rapid duplicate awards

## Debugging Event Flow

### Enable Debug Logging

```python
# In joystick.py
joystick_client.debug = True
```

Outputs all raw WebSocket messages.

### Trace an Event

Add logging at each stage:

```python
logger.info(f"[1-CAPTURE] Received {event_type} for {user}")
logger.info(f"[2-NORMALIZE] Parsed: type={event_type}, user={user}, metadata={metadata}")
logger.info(f"[3-DISPATCH] Calling on_{event_type}({user})")
logger.info(f"[4-COOLDOWN] Active={is_active}, Remaining={remaining}s")
logger.info(f"[5-REWARD] Granted {points}pts, {xp}xp")
logger.info(f"[6-LEVELUP] {level_before} → {level_after}")
logger.info(f"[7-SIDEEFFECT] Queued TTS: {message}")
logger.info(f"[8-COOLDOWN] Set {key} for {duration}s")
```

### Simulate Events

For testing without live stream:

```python
await joystick_client.sim_push_chat("testuser", "hello")
await joystick_client.sim_push_tip("testuser", 100)
await joystick_client.sim_push_follow("testuser")
```

## See Also

- [Points System](points-system.md) - Point reward details
- [XP & Leveling](xp-leveling.md) - XP calculation and rewards
- [Joystick Integration](joystick-integration.md) - Event source details
- [Customization Guide](customization.md) - Adding custom event handlers

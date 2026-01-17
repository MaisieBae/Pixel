# Points System

The Points System is Pixel Bot's virtual currency that rewards user engagement and enables interactive features.

## Overview

Points are awarded automatically for stream interactions and can be spent on redeems, wheel spins, or custom features. All point transactions are logged for transparency and auditing.

## Architecture

### Service Class: `PointsService`

**Location**: `app/core/points.py`

The `PointsService` class handles all point operations:

```python
class PointsService:
    def ensure_user(name: str) -> User
    def get_balance(user_id: int) -> int
    def grant(user_id: int, amount: int, reason: str) -> int
    def spend(user_id: int, amount: int, reason: str) -> int
    def adjust(user_id: int, delta: int, reason: str, allow_negative_balance: bool) -> int
    def list_transactions(user_id: int, limit: int) -> list[Transaction]
```

### Database Schema

**users** table:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP,
    last_seen TIMESTAMP
);
```

**points** table:
```sql
CREATE TABLE points (
    user_id INTEGER PRIMARY KEY,  -- 1:1 with users
    balance INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**transactions** table:
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,  -- 'grant', 'spend', 'adjust'
    delta INTEGER NOT NULL,  -- Can be positive or negative
    reason TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Earning Points

### Chat Messages

**Configuration**:
```ini
POINTS_CHAT_AMOUNT=1
POINTS_CHAT_COOLDOWN_SECONDS=60
```

**Behavior**:
- User sends a chat message
- If cooldown expired, award `POINTS_CHAT_AMOUNT` points
- Set cooldown for `POINTS_CHAT_COOLDOWN_SECONDS`
- Prevents spam by limiting frequency

**Code Flow**:
```python
# In consumers.py
async def on_chat(user: str, text: str):
    if not settings.POINTS_ENABLED:
        return
    
    u = points_service.ensure_user(user)
    
    # Check cooldown
    active, remaining = cooldowns.is_active(u.id, "points:chat")
    if active:
        return  # Still on cooldown
    
    # Grant points
    amount = settings.POINTS_CHAT_AMOUNT
    points_service.grant(u.id, amount, reason="chat")
    
    # Set new cooldown
    cooldowns.set(u.id, "points:chat", settings.POINTS_CHAT_COOLDOWN_SECONDS)
```

### Follows

**Configuration**:
```ini
POINTS_FOLLOW_AMOUNT=50
```

**Behavior**:
- User follows the channel
- Award `POINTS_FOLLOW_AMOUNT` points immediately
- No cooldown (one-time event)

### Drop-ins (Entering Stream)

**Configuration**:
```ini
POINTS_DROPIN_AMOUNT=25
POINTS_DROPIN_COOLDOWN_SECONDS=3600  # Once per stream
```

**Behavior**:
- User enters the stream (detected via UserPresence event)
- Award points if cooldown expired
- Cooldown prevents multiple awards in same stream

### Subscriptions

**Configuration**:
```ini
POINTS_SUB_AMOUNT=200
```

**Behavior**:
- User subscribes or gifts a sub
- Award `POINTS_SUB_AMOUNT` points
- Multi-month subs multiply the amount

**Example**:
```python
# User subs for 3 months
amount = settings.POINTS_SUB_AMOUNT * months  # 200 * 3 = 600 points
```

### Tips

**Configuration**:
```ini
POINTS_TIP_PER_TOKEN=1.0
POINTS_TIP_COOLDOWN_SECONDS=30
```

**Behavior**:
- User tips tokens
- Points = `tokens × POINTS_TIP_PER_TOKEN`
- Cooldown applies to prevent rapid small tips from flooding rewards

**Example**:
```python
# User tips 100 tokens
points = 100 * 1.0 = 100 points
```

## Spending Points

### Redeem Handlers

Points can be spent on custom redeems. Each redeem handler checks balance and calls `spend()`:

```python
# In redeems.py
async def handle_custom_redeem(event_data: dict):
    user_name = event_data.get("user")
    cost = 500  # Define cost
    
    with SessionLocal() as db:
        points = PointsService(db)
        u = points.ensure_user(user_name)
        
        # Check balance
        if points.get_balance(u.id) < cost:
            await send_message(f"@{user_name} you need {cost} points!")
            return
        
        # Spend points
        try:
            new_balance = points.spend(u.id, cost, reason="custom_redeem")
            await trigger_effect()
            await send_message(f"@{user_name} spent {cost} points! New balance: {new_balance}")
        except ValueError as e:
            await send_message(f"@{user_name} error: {e}")
```

### Validation

The `spend()` method includes validation:
```python
def spend(self, user_id: int, amount: int, reason: str) -> int:
    pts = self.db.get(Points, user_id)
    if pts is None or pts.balance < amount:
        raise ValueError("Insufficient points")
    
    pts.balance -= amount
    self.db.add(Transaction(
        user_id=user_id,
        type="spend",
        delta=-amount,
        reason=reason
    ))
    self.db.commit()
    return pts.balance
```

## Admin Operations

### Manual Adjustments

Admins can manually adjust points via the dashboard or API:

```python
points.adjust(
    user_id=5,
    delta=1000,  # Positive to add, negative to remove
    reason="event_bonus",
    allow_negative_balance=False  # Prevent going below 0
)
```

### Batch Operations

**See**: [Batch Operations Documentation](batch-operations.md)

Admins can adjust points for multiple users at once:

```
POST /admin/api/users/batch-points
{
  "operation": "add",
  "amount": 500,
  "target": "all",
  "reason": "holiday_event"
}
```

## Transaction History

Every point change is recorded:

```python
transactions = points.list_transactions(user_id=5, limit=50)

for tx in transactions:
    print(f"{tx.created_at}: {tx.type} {tx.delta} ({tx.reason})")
```

**Output**:
```
2026-01-16 19:30:00: grant +1 (chat)
2026-01-16 19:25:00: grant +100 (tip)
2026-01-16 19:20:00: spend -500 (wheel_spin)
2026-01-16 19:15:00: grant +50 (follow)
```

## Starting Balance

New users can receive starting points:

**Configuration**:
```ini
POINTS_START_AMOUNT=100
```

**Implementation**:
```python
def ensure_user(self, name: str) -> User:
    user = db.scalar(select(User).where(User.name == name))
    is_new = False
    
    if user is None:
        user = User(name=name)
        db.add(user)
        db.flush()
        
        # Create points record
        db.add(Points(user_id=user.id, balance=0))
        is_new = True
    
    # Grant starting points for new users
    if is_new and self.settings.POINTS_START_AMOUNT > 0:
        pts = db.get(Points, user.id)
        pts.balance = self.settings.POINTS_START_AMOUNT
        db.add(Transaction(
            user_id=user.id,
            type="grant",
            delta=self.settings.POINTS_START_AMOUNT,
            reason="start"
        ))
    
    db.commit()
    return user
```

## Cooldown System

**Location**: `app/core/cooldowns.py`

Cooldowns prevent users from earning points too frequently:

```python
class CooldownService:
    def is_active(user_id: int, key: str) -> tuple[bool, int]:
        # Returns (is_active, seconds_remaining)
    
    def set(user_id: int, key: str, duration_seconds: int):
        # Sets cooldown for duration
```

**Cooldown Keys**:
- `points:chat` - Chat message cooldown
- `points:tip` - Tip cooldown
- `points:dropin` - Drop-in cooldown
- `points:follow` - Follow cooldown (rarely used)

**Storage**: In-memory dictionary (not persisted across restarts)

## Configuration Reference

### Enable/Disable
```ini
POINTS_ENABLED=true
```

### Starting Balance
```ini
POINTS_START_AMOUNT=100
```

### Chat Rewards
```ini
POINTS_CHAT_AMOUNT=1
POINTS_CHAT_COOLDOWN_SECONDS=60
```

### Event Rewards
```ini
POINTS_FOLLOW_AMOUNT=50
POINTS_DROPIN_AMOUNT=25
POINTS_SUB_AMOUNT=200
```

### Tip Rewards
```ini
POINTS_TIP_PER_TOKEN=1.0
POINTS_TIP_COOLDOWN_SECONDS=30
```

## Best Practices

### Setting Point Values

1. **Chat messages**: Low value (1-5) to reward engagement without inflation
2. **Follows**: Medium value (25-100) for one-time reward
3. **Subs**: High value (200-500) for monetary support
4. **Tips**: Scale with token value (0.5-2.0 per token)

### Cooldowns

1. **Chat**: 30-120 seconds to balance engagement vs. spam
2. **Tips**: 10-30 seconds to allow multiple tips but prevent abuse
3. **Drop-ins**: 3600 seconds (1 hour) to limit to once per stream

### Redeem Costs

1. **Simple effects**: 100-500 points
2. **TTS messages**: 200-1000 points
3. **Wheel spins**: 500-2000 points
4. **Premium effects**: 1000+ points

## Troubleshooting

### Points not being awarded

1. Check `POINTS_ENABLED=true` in `.env`
2. Verify cooldown settings aren't too long
3. Check logs for database errors
4. Ensure user exists: `points.ensure_user(username)`

### Insufficient points errors

1. Check balance: `points.get_balance(user_id)`
2. Review transaction history
3. Verify spend amount matches redeem cost

### Negative balances

1. By default, `spend()` prevents negative balances
2. Admin `adjust()` can allow negative if `allow_negative_balance=True`
3. Check transaction log for unauthorized adjustments

## Example Workflows

### User Journey

```
1. Alice joins stream → +25 points (dropin)
2. Alice sends chat "hello" → +1 point (chat)
3. Alice waits 60 seconds
4. Alice sends chat "cool stream" → +1 point (chat)
5. Alice follows channel → +50 points (follow)
6. Alice tips 100 tokens → +100 points (tip)

Total: 177 points
```

### Redeem Flow

```
1. Alice has 177 points
2. Alice redeems "Spin Wheel" (costs 100 points)
3. Bot checks balance: 177 >= 100 ✓
4. Bot calls points.spend(alice.id, 100, "wheel_spin")
5. Transaction logged: spend -100 (wheel_spin)
6. New balance: 77 points
7. Wheel effect triggered
```

## See Also

- [XP & Leveling](xp-leveling.md) - Companion progression system
- [Batch Operations](batch-operations.md) - Bulk point management
- [Database Schema](database-schema.md) - Complete data model
- [Admin Dashboard](admin-dashboard.md) - Managing points via UI

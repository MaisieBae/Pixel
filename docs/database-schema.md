# Database Schema

Pixel Bot uses SQLite with SQLAlchemy ORM for data persistence.

## Overview

**Database File**: `./data/pixel.db`
**ORM**: SQLAlchemy
**Location**: `app/core/models.py`

## Tables

### users

Stores user accounts and point balances.

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    points INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Columns**:
- `id` - Primary key
- `name` - Username (unique)
- `points` - Current point balance
- `created_at` - Account creation timestamp
- `updated_at` - Last modification timestamp

**Indexes**:
- `users.name` (unique)

### xp_records

Tracks user XP and levels.

```sql
CREATE TABLE xp_records (
    id INTEGER PRIMARY KEY,
    user_name TEXT UNIQUE NOT NULL,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Columns**:
- `id` - Primary key
- `user_name` - Username (unique)
- `xp` - Total XP earned
- `level` - Current level
- `created_at` - Record creation
- `updated_at` - Last XP/level change

**Indexes**:
- `xp_records.user_name` (unique)

### transactions

Logs all point transactions.

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT,
    balance_after INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Columns**:
- `id` - Primary key
- `user_id` - Foreign key to users table
- `amount` - Points added (positive) or removed (negative)
- `reason` - Transaction description (e.g., "chat", "tip", "redeem:tts")
- `balance_after` - User's balance after transaction
- `created_at` - Transaction timestamp

**Indexes**:
- `transactions.user_id`
- `transactions.created_at`

### cooldowns

Tracks user cooldown timers.

```sql
CREATE TABLE cooldowns (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE (user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Columns**:
- `id` - Primary key
- `user_id` - Foreign key to users
- `key` - Cooldown identifier (e.g., "chat", "tts", "wheel")
- `expires_at` - When cooldown expires

**Indexes**:
- `(user_id, key)` (unique composite)
- `cooldowns.expires_at`

### queue_items

Manages action queues (TTS, wheel, effects).

```sql
CREATE TABLE queue_items (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    payload_json JSON,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
```

**Columns**:
- `id` - Primary key
- `kind` - Queue type ("tts", "wheel", "effect")
- `status` - "pending", "running", "done", "failed"
- `payload_json` - Queue item data (JSON)
- `created_at` - When queued
- `started_at` - When processing began
- `finished_at` - When completed

**Indexes**:
- `(kind, status)`
- `queue_items.created_at`

### redeems

Configures point redemptions.

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

**Columns**:
- `key` - Redeem identifier (primary key)
- `display_name` - User-friendly name
- `cost` - Points required
- `enabled` - Whether active
- `cooldown_s` - Cooldown duration in seconds
- `created_at` - When created
- `updated_at` - Last modified

**Default Redeems**:
- `tts` - Text-to-Speech
- `pixel` - AI chat response
- `sound` - Play sound effect
- `spin` - Prize wheel
- `clip` - Save OBS clip

### joystick_installs

Stores Joystick.tv OAuth tokens.

```sql
CREATE TABLE joystick_installs (
    id INTEGER PRIMARY KEY,
    channel_id TEXT UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Columns**:
- `id` - Primary key
- `channel_id` - Joystick channel ID (unique)
- `access_token` - OAuth access token
- `refresh_token` - OAuth refresh token
- `expires_at` - Token expiration
- `created_at` - Installation date
- `updated_at` - Last token refresh

## Relationships

### User → Transactions

**One-to-Many**: One user has many transactions.

```python
user = db.get(User, 1)
transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
```

### User → Cooldowns

**One-to-Many**: One user has many cooldowns.

```python
user = db.get(User, 1)
cooldowns = db.query(Cooldown).filter(Cooldown.user_id == user.id).all()
```

### User → XP Record

**One-to-One**: One user has one XP record.

```python
user_name = "alice"
xp_record = db.query(XPRecord).filter(XPRecord.user_name == user_name).first()
```

## Common Queries

### Get User with Balance

```python
user = db.scalar(select(User).where(User.name == "alice"))
print(f"{user.name}: {user.points} points")
```

### Get Recent Transactions

```python
txns = db.scalars(
    select(Transaction)
    .where(Transaction.user_id == user.id)
    .order_by(Transaction.created_at.desc())
    .limit(10)
)
```

### Check Active Cooldown

```python
from datetime import datetime

cooldown = db.scalar(
    select(Cooldown)
    .where(
        Cooldown.user_id == user.id,
        Cooldown.key == "tts",
        Cooldown.expires_at > datetime.utcnow()
    )
)

if cooldown:
    remaining = (cooldown.expires_at - datetime.utcnow()).total_seconds()
    print(f"Cooldown: {remaining}s remaining")
```

### Get Pending Queue Items

```python
pending = db.scalars(
    select(QueueItem)
    .where(QueueItem.kind == "tts", QueueItem.status == "pending")
    .order_by(QueueItem.id.asc())
)
```

### Get Top Users by Points

```python
top_users = db.scalars(
    select(User)
    .order_by(User.points.desc())
    .limit(10)
)
```

### Get Top Users by XP

```python
top_xp = db.scalars(
    select(XPRecord)
    .order_by(XPRecord.xp.desc())
    .limit(10)
)
```

## Maintenance

### Cleanup Old Cooldowns

```python
from datetime import datetime, timedelta

# Delete expired cooldowns older than 1 hour
expired = datetime.utcnow() - timedelta(hours=1)
db.query(Cooldown).filter(Cooldown.expires_at < expired).delete()
db.commit()
```

### Cleanup Old Queue Items

```python
# Delete completed items older than 7 days
old_date = datetime.utcnow() - timedelta(days=7)
db.query(QueueItem).filter(
    QueueItem.status.in_(["done", "failed"]),
    QueueItem.finished_at < old_date
).delete()
db.commit()
```

### Vacuum Database

```python
# Reclaim space from deleted records
db.execute(text("VACUUM"))
```

## Backup

### Manual Backup

```bash
cp ./data/pixel.db ./data/pixel.db.backup
```

### Automated Backup

```python
import shutil
from datetime import datetime

def backup_database():
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    source = "./data/pixel.db"
    dest = f"./data/backups/pixel_{timestamp}.db"
    shutil.copy2(source, dest)
    print(f"Backup created: {dest}")

# Run daily
scheduler.add_job(backup_database, "cron", hour=3)
```

## Migrations

### Adding a Column

```python
# Using Alembic or raw SQL
from sqlalchemy import text

db.execute(text("ALTER TABLE users ADD COLUMN display_name TEXT"))
db.commit()
```

### Adding a Table

```python
# Define model in models.py
class NewTable(Base):
    __tablename__ = "new_table"
    id = Column(Integer, primary_key=True)
    # ... columns ...

# Create table
Base.metadata.create_all(engine)
```

## See Also

- [Systems Overview](systems-overview.md) - Architecture
- [Points System](points-system.md) - Points/transactions
- [XP System](xp-leveling.md) - XP/levels
- [Event Flow](event-flow.md) - Queue processing

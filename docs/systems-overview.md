# Systems Overview

Pixel Bot is built on a modular architecture that separates concerns and allows for easy extension. This document provides a high-level overview of how the systems work together.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Joystick.tv Platform                    │
│              (Chat, Tips, Follows, Subs, etc.)              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ WebSocket (ActionCable)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    JoystickClient                           │
│              (app/core/joystick.py)                         │
│         ┌───────────────────────────────────────┐           │
│         │   Event Parsing & Normalization       │           │
│         └───────────────┬───────────────────────┘           │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Event Consumers                           │
│               (app/core/consumers.py)                       │
│         ┌───────────────────────────────────────┐           │
│         │  Route events to appropriate handlers │           │
│         └───────────────┬───────────────────────┘           │
└─────────────────────────┼───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌────────┐      ┌─────────┐      ┌──────────┐
    │ Points │      │   XP    │      │ Redeems  │
    │ System │      │ System  │      │  System  │
    └────┬───┘      └────┬────┘      └────┬─────┘
         │               │                │
         └───────────────┼────────────────┘
                         ▼
              ┌─────────────────────┐
              │   SQLite Database   │
              │  (users, points,    │
              │   xp, transactions) │
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Queue System      │
              │  (TTS, Effects,     │
              │   Notifications)    │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌────────┐     ┌──────────┐    ┌─────────┐
    │  TTS   │     │  Wheel   │    │  OBS    │
    │ Engine │     │  Spins   │    │ Control │
    └────────┘     └──────────┘    └─────────┘
```

## Core Components

### 1. Web Server (FastAPI)

**Location**: `app/main.py`, `app/admin/server.py`

The bot runs a FastAPI web server that provides:
- Admin dashboard UI at `/admin`
- REST API endpoints for management
- OAuth callback handling
- WebSocket endpoints for real-time updates
- Static file serving for overlays

### 2. Joystick Integration Layer

**Location**: `app/core/joystick.py`, `app/core/joystick_oauth.py`

Handles all communication with Joystick.tv:
- **OAuth Flow**: Authenticates streamers and stores access tokens
- **WebSocket Connection**: Maintains persistent connection via ActionCable
- **Event Parsing**: Normalizes incoming events (chat, tips, follows, etc.)
- **Message Sending**: Sends chat messages and whispers back to Joystick

**Event Types Handled**:
- `ChatMessage` - User chat messages
- `UserPresence` - Users entering/leaving stream
- `StreamEvent` - Tips, follows, subs, and other stream events

### 3. Event Consumer System

**Location**: `app/core/consumers.py`

The central event router that:
- Receives normalized events from JoystickClient
- Dispatches events to appropriate service handlers
- Manages cooldowns and rate limiting
- Triggers side effects (TTS, notifications, etc.)

**Consumer Functions**:
```python
async def on_chat(user: str, text: str)
async def on_follow(user: str)
async def on_sub(user: str, months: int)
async def on_tip(user: str, tokens: int)
async def on_dropin(user: str)
```

### 4. Points System

**Location**: `app/core/points.py`

**Purpose**: Manage virtual currency for users

**Key Features**:
- Grant points for activities (chat, tips, follows)
- Spend points on redeems
- Admin adjustments
- Transaction history
- Starting balance for new users

**Database Tables**:
- `users` - User profiles
- `points` - Current balances (1:1 with users)
- `transactions` - Points history

### 5. XP & Leveling System

**Location**: `app/core/xp.py`, `app/core/xp_curve.py`

**Purpose**: Progressive leveling system with rewards

**Key Features**:
- Award XP for activities
- Calculate levels using configurable curve (base × level^exponent)
- Level-up rewards (points, messages, TTS)
- Transaction history
- Progress tracking

**Database Tables**:
- `xp` - User XP totals and levels (1:1 with users)
- `xp_transactions` - XP history

### 6. Redeem System

**Location**: `app/core/redeems.py`

**Purpose**: Handle channel point redeems

**Key Features**:
- Extensible handler registration
- Cooldown management
- Cost validation
- Effect triggering (TTS, sounds, OBS)

### 7. Queue System

**Location**: `app/core/queue.py`

**Purpose**: Manage async operations that need sequential processing

**Queue Types**:
- `tts` - Text-to-speech requests
- `wheel` - Prize wheel spins
- `effect` - Visual/audio effects

**Database Table**: `queue_items`

### 8. TTS Engine

**Location**: `app/core/tts.py`

**Purpose**: Convert text to speech with queueing

**Features**:
- Queue management (max 5 by default)
- Pre-sound announcements
- Username prefixing
- Cooldowns per user
- Volume normalization

### 9. Database Layer

**Location**: `app/core/models.py`, `app/core/db.py`

**Technology**: SQLAlchemy ORM with SQLite

**Key Models**:
- `User` - User profiles and metadata
- `Points` - Point balances
- `XP` - XP totals and levels
- `Transaction` - Points transaction log
- `XPTransaction` - XP transaction log
- `QueueItem` - Async operation queue
- `JoystickInstall` - OAuth installations

## Data Flow Examples

### Example 1: User Sends Chat Message

```
1. Joystick.tv → WebSocket → JoystickClient
2. JoystickClient parses ChatMessage event
3. Calls on_chat(user="alice", text="hello")
4. Consumer checks if XP/Points systems enabled
5. Consumer checks cooldowns
6. PointsService.grant(user_id, 1, reason="chat")
7. XpService.handle_event(type="chat", user="alice")
8. Database records transactions
9. Cooldowns set for next chat reward
```

### Example 2: User Tips Streamer

```
1. Joystick.tv → StreamEvent (Tipped) → JoystickClient
2. JoystickClient parses metadata (who, how_much)
3. Calls on_tip(user="bob", tokens=100)
4. Consumer calculates rewards:
   - Points: 100 tokens × 1.0 = 100 points
   - XP: 100 tokens × 0.1 = 10 XP
5. PointsService.grant(user_id, 100, reason="tip")
6. XpService.handle_event(type="tip", tokens=100)
7. XpService detects level-up (4 → 5)
8. LevelRewards applies rewards (500 bonus points)
9. QueueItem created for TTS: "Bob reached level 5!"
10. TTS queue processor picks up item
11. Audio file generated and played
```

### Example 3: Admin Batch Operation

```
1. Admin navigates to /admin → Batch Operations tab
2. Submits: "Add 1000 points to all users"
3. POST /admin/api/users/batch-points
4. Server queries all users from database
5. For each user:
   - PointsService.adjust(user_id, +1000, reason="event")
   - Transaction recorded
6. Response sent: {success: 150, failed: 0}
7. Admin UI refreshes user list
```

## Configuration System

**Location**: `app/core/config.py`

All settings are loaded from `.env` file using Pydantic settings:

```python
class Settings(BaseSettings):
    # Loaded from .env
    JOYSTICK_CLIENT_ID: str
    POINTS_ENABLED: bool = True
    XP_BASE: int = 100
    # ... etc
```

Settings are injected into services at initialization.

## Error Handling

### Graceful Degradation

- If Joystick connection fails, bot retries with exponential backoff
- If Points/XP services error, user interaction continues
- If TTS fails, error logged but bot continues
- Database transactions are atomic (rollback on error)

### Logging

All major operations log to console:
```
[joystick] connected
[consumer] chat: alice said hello
[points] granted 1 to user_id=5 (chat)
[xp] awarded 1 XP to alice (chat)
```

## Performance Considerations

### Database
- SQLite for simplicity (suitable for single-bot use)
- Indexes on frequently queried fields (user_id, created_at)
- Transactions batched where possible

### Concurrency
- FastAPI runs async (uvicorn)
- Event handlers are async functions
- Database operations use connection pooling

### Cooldowns
- In-memory cooldown tracking (not persistent)
- Per-user, per-event-type cooldowns
- Prevents spam and reduces database writes

## Extension Points

The bot is designed to be extended:

1. **New Event Handlers**: Add to `consumers.py`
2. **New Redeems**: Add to `redeems.py` handler registry
3. **New Effects**: Create modules in `app/core/effects/`
4. **New Admin Endpoints**: Add to `app/admin/server.py`
5. **New Database Models**: Add to `models.py` and run migrations

## Next Steps

- [Points System](points-system.md) - Deep dive into currency
- [XP & Leveling](xp-leveling.md) - Understanding progression
- [Event Flow](event-flow.md) - Detailed event lifecycle
- [Customization Guide](customization.md) - Extending the bot

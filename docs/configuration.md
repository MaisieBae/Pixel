# Configuration Guide

Complete reference for all Pixel Bot configuration options.

## Configuration File

**Location**: `.env` in project root

**Format**: Key-value pairs

```ini
KEY=value
ANOTHER_KEY=some value
```

## Core Settings

### Bot Identity

```ini
# Bot username for filtering own messages
BOT_USERNAME=pixel
```

### Database

```ini
# SQLite database file
DATABASE_URL=sqlite:///./data/pixel.db
```

## Joystick.tv Integration

### OAuth Credentials

```ini
# OAuth application credentials
JOYSTICK_CLIENT_ID=your-client-id
JOYSTICK_CLIENT_SECRET=your-client-secret
JOYSTICK_REDIRECT_URI=http://localhost:8080/oauth/callback
```

### WebSocket Connection

```ini
# ActionCable WebSocket gateway key
JOYSTICK_BASIC_KEY=your-basic-key

# Default channel for bot messages
JOYSTICK_DEFAULT_CHANNEL_ID=channel123
```

## Points System

### Earning Points

```ini
# Points per chat message
POINTS_PER_CHAT=10

# Cooldown between chat point awards (seconds)
CHAT_COOLDOWN_SECONDS=60

# Points for following
POINTS_PER_FOLLOW=500

# Points for subscribing
POINTS_PER_SUB=1000

# Multiplier for sub months
POINTS_SUB_MONTH_MULTIPLIER=100

# Points for tipping (per token)
POINTS_PER_TIP_TOKEN=10

# Points for dropping in
POINTS_PER_DROPIN=100
```

### Transaction Logging

```ini
# Log all point transactions to database
LOG_TRANSACTIONS=true
```

## XP System

### Earning XP

```ini
# XP per chat message
XP_PER_CHAT=10

# Cooldown between chat XP awards (seconds)
XP_CHAT_COOLDOWN_SECONDS=60

# XP for following
XP_PER_FOLLOW=100

# XP for subscribing
XP_PER_SUB=500

# XP per tip token
XP_PER_TIP_TOKEN=5

# XP for dropping in
XP_PER_DROPIN=50
```

### Leveling Curve

```ini
# Base XP for level 2
XP_BASE=100

# Growth factor between levels
XP_FACTOR=1.3

# Level rewards configuration file
LEVEL_REWARDS_FILE=./data/level_rewards.json
```

## Redeems

Redeems are configured in the database. See [Redeems System](redeems.md).

## TTS System

```ini
# Pre-roll sound effect
TTS_PRE_SOUND=announcement.wav

# Maximum pending TTS messages
TTS_QUEUE_MAX=5

# Cooldown between TTS redeems (seconds)
TTS_COOLDOWN_SECONDS=10

# Prefix username to message
TTS_PREFIX_USERNAME=true

# Delay between pre-sound and speech (milliseconds)
TTS_PRE_DELAY_MS=1200
```

## AI Chat (Pixel)

### Perplexity API

```ini
# API key (required for AI features)
PPLX_API_KEY=your-perplexity-api-key

# Model to use
PPLX_MODEL=sonar-small-online

# Maximum tokens in response
PPLX_MAX_TOKENS=200

# API timeout (seconds)
PPLX_TIMEOUT=12
```

### Response Behavior

```ini
# Probability of random replies (0.0-1.0)
PPLX_RANDOM_REPLY_PROB=0.08

# Maximum response length (characters)
PIXEL_MAX_CHARS=220

# Maximum sentences in response
PIXEL_MAX_SENTENCES=2
```

## Prize Wheel

```ini
# Prize configuration file
PRIZES_FILE=./data/prizes.json

# Announcement line files
SPIN_LINES_FILE=./data/spin_lines.txt
PRIZE_LINES_FILE=./data/prize_lines.txt

# Sound effects
WHEEL_SFX_START=wheel_start.wav
WHEEL_SFX_LOOP=wheel_loop.wav
WHEEL_SFX_WIN=wheel_win.wav

# Animation duration range (seconds)
WHEEL_SPIN_MIN=2
WHEEL_SPIN_MAX=10

# Wheel image for overlay
WHEEL_IMAGE_URL=/admin/static/wheel/question.png

# Delay before TTS announcement (milliseconds)
WHEEL_PRE_TTS_DELAY_MS=900
```

## OBS Integration

```ini
# Enable OBS features
OBS_ENABLED=true

# WebSocket connection
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your-obs-password
```

## Admin Dashboard

```ini
# Web server port
ADMIN_PORT=8080

# Admin password (hashed)
ADMIN_PASSWORD_HASH=your-hashed-password

# Session secret key
SECRET_KEY=your-random-secret-key
```

## File Paths

### Data Files

```ini
# Base data directory
DATA_DIR=./data

# Level rewards
LEVEL_REWARDS_FILE=./data/level_rewards.json

# Prize wheel
PRIZES_FILE=./data/prizes.json
SPIN_LINES_FILE=./data/spin_lines.txt
PRIZE_LINES_FILE=./data/prize_lines.txt

# Sounds directory
SOUNDS_DIR=./sounds
```

## Logging

```ini
# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Log file location
LOG_FILE=./logs/pixel.log

# Log format
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

## Advanced Settings

### Queue Processing

```ini
# Queue poll interval (seconds)
QUEUE_POLL_INTERVAL=1.0

# Maximum concurrent queue processors
QUEUE_MAX_WORKERS=3
```

### Rate Limiting

```ini
# Minimum time between messages (seconds)
MESSAGE_RATE_LIMIT=1.0

# Maximum messages per minute
MAX_MESSAGES_PER_MINUTE=20
```

### Cooldown Cleanup

```ini
# Cleanup expired cooldowns (hours)
COOLDOWN_CLEANUP_HOURS=1

# Run cleanup interval (minutes)
CLEANUP_INTERVAL_MINUTES=60
```

## Environment-Specific Configs

### Development

```ini
# .env.development
LOG_LEVEL=DEBUG
ADMIN_PORT=8080
OBS_ENABLED=false
```

### Production

```ini
# .env.production
LOG_LEVEL=INFO
ADMIN_PORT=80
OBS_ENABLED=true
```

### Testing

```ini
# .env.test
DATABASE_URL=sqlite:///./data/test.db
LOG_LEVEL=WARNING
```

## Loading Configuration

### In Code

```python
from app.core.config import Settings

settings = Settings()  # Loads from .env
print(settings.BOT_USERNAME)
print(settings.POINTS_PER_CHAT)
```

### Environment Override

```bash
# Override specific setting
POINTS_PER_CHAT=20 python main.py
```

### Multiple Environments

```bash
# Load specific .env file
python main.py --env production
```

## Validation

### Required Settings

These must be set:
- `BOT_USERNAME`
- `JOYSTICK_CLIENT_ID`
- `JOYSTICK_CLIENT_SECRET`
- `JOYSTICK_BASIC_KEY`

### Optional Settings

These have defaults:
- `POINTS_PER_CHAT` (default: 10)
- `XP_PER_CHAT` (default: 10)
- `LOG_LEVEL` (default: INFO)

### Validation Errors

```python
from app.core.config import Settings

try:
    settings = Settings()
except Exception as e:
    print(f"Configuration error: {e}")
```

## Security Best Practices

### Never Commit .env

Add to `.gitignore`:
```
.env
.env.*
!.env.example
```

### Use .env.example

Provide template:
```ini
# .env.example
BOT_USERNAME=your_bot_name
JOYSTICK_CLIENT_ID=your_client_id
JOYSTICK_CLIENT_SECRET=your_client_secret
```

### Rotate Secrets

Regularly change:
- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- API keys

## Troubleshooting

### Setting Not Loading

1. Check spelling (case-sensitive)
2. Verify `.env` file location
3. Check for quotes (usually not needed)
4. Restart application

### Invalid Values

1. Check data type (number vs string)
2. Verify boolean format (true/false)
3. Check file paths exist

### Missing Required Settings

```
Configuration error: JOYSTICK_CLIENT_ID is required
```

Add missing setting to `.env`.

## See Also

- [Systems Overview](systems-overview.md) - Architecture
- [Points System](points-system.md) - Points configuration
- [XP System](xp-leveling.md) - XP configuration
- [AI Chat](ai-chat.md) - Perplexity settings

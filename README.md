# Pixel Bot

A feature-rich interactive streaming bot for Joystick.tv that engages your community through gamification, chat interactions, and automated rewards.

## Overview

Pixel is a Python-based bot designed for Joystick.tv streamers. It provides a comprehensive points and XP system, interactive features like prize wheels and redeems, text-to-speech capabilities, and real-time chat interactions powered by AI. The bot includes a web-based admin dashboard for easy management and monitoring.

## Features

### Core Systems
- **Points & Currency System** - Award points for chat activity, follows, subs, and tips
- **XP & Leveling** - Progressive leveling system with customizable XP curves and level rewards
- **User Management** - Track user stats, transactions, and engagement metrics
- **Batch Operations** - Bulk adjust points/XP for multiple users (events, corrections, etc.)

### Interactive Features
- **Channel Point Redeems** - Custom redeem handlers with cooldowns
- **Prize Wheel** - Spin-the-wheel mechanics with customizable prizes and sound effects
- **Text-to-Speech (TTS)** - Queue-based TTS system with pre-sounds and username prefixes
- **AI Chat Responses** - Perplexity AI integration for intelligent bot replies
- **Sound Effects** - Trigger audio files for various events

### Integrations
- **Joystick.tv** - OAuth authentication, ActionCable WebSocket, chat integration
- **OBS WebSocket** - Control OBS for clips and scene management
- **VRChat OSC** - Optional VRChat integration for in-game events
- **Browser Extension** - Tip clicker extension for automated tip detection

### Admin Dashboard
- Web-based control panel at `/admin`
- Real-time user statistics and leaderboards
- Transaction history and audit logs
- Settings management
- Batch operations interface

## Requirements

- Python 3.10+
- SQLite (included with Python)
- Joystick.tv account with OAuth credentials
- Optional: OBS Studio with WebSocket plugin

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/MaisieBae/Pixel.git
cd Pixel
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- FastAPI & Uvicorn (web server)
- SQLAlchemy (database)
- Pydantic (configuration)
- WebSockets (real-time communication)
- aiohttp (async HTTP client)
- obsws-python (OBS integration)
- Additional utilities (jinja2, python-dotenv, etc.)

### 3. Configure Environment

Create or edit the `.env` file in the root directory with your settings:

```ini
# Bot Identity
BOT_USERNAME=pixel

# Server Configuration
APP_HOST=0.0.0.0
APP_PORT=8080

# Admin Security (optional)
ADMIN_TOKEN=your-secret-token

# Joystick.tv OAuth Credentials
JOYSTICK_CLIENT_ID=your-client-id
JOYSTICK_CLIENT_SECRET=your-client-secret
JOYSTICK_REDIRECT_URI=http://localhost:8080/oauth/callback
JOYSTICK_BASIC_KEY=your-basic-key

# Optional: Default Channel
JOYSTICK_DEFAULT_CHANNEL_ID=

# Points System
POINTS_ENABLED=true
POINTS_CHAT_AMOUNT=1
POINTS_CHAT_COOLDOWN_SECONDS=60
POINTS_FOLLOW_AMOUNT=50
POINTS_DROPIN_AMOUNT=25
POINTS_SUB_AMOUNT=200
POINTS_TIP_PER_TOKEN=1.0

# XP & Leveling
XP_ENABLED=true
XP_BASE=100
XP_EXPONENT=1.8
XP_MAX_LEVEL=9999
XP_CHAT_AMOUNT=1
XP_FOLLOW_AMOUNT=10
XP_SUB_AMOUNT=50
XP_TIP_PER_TOKEN=0.1

# Perplexity AI (for chat responses)
PPLX_API_KEY=your-perplexity-api-key
PPLX_MODEL=sonar-small-online
PPLX_RANDOM_REPLY_PROB=0.08
PPLX_MAX_TOKENS=200

# TTS Configuration
TTS_PRE_SOUND=announcement.wav
TTS_QUEUE_MAX=5
TTS_COOLDOWN_SECONDS=10
TTS_PREFIX_USERNAME=true

# Prize Wheel
PRIZES_FILE=./data/prizes.json
WHEEL_SPIN_MIN=2
WHEEL_SPIN_MAX=10

# OBS WebSocket
OBS_WS_ENABLED=true
OBS_WS_HOST=localhost
OBS_WS_PORT=4455
OBS_WS_PASSWORD=your-obs-password

# VRChat OSC (optional)
VRC_OSC_ENABLED=false
VRC_OSC_HOST=127.0.0.1
VRC_OSC_PORT=9000

# Tip Tiers
TIP_LOW_MAX=14
TIP_MEDIUM_MAX=100
TIP_HIGH_MAX=500
TIP_EXTREME_MAX=1000
```

### 4. Set Up Data Files

Create the `data` directory and configuration files:

```bash
mkdir -p data
```

**data/prizes.json** (example):
```json
[
  {"name": "100 Points", "weight": 30},
  {"name": "500 Points", "weight": 15},
  {"name": "1000 XP", "weight": 10},
  {"name": "Mystery Prize", "weight": 5}
]
```

**data/level_rewards.json** (optional):
```json
{
  "5": {"points": 500, "message": "You reached level 5!"},
  "10": {"points": 1000, "message": "You reached level 10!"},
  "25": {"points": 5000, "message": "Quarter century!"}
}
```

**data/spin_lines.txt** - Lines said when wheel starts
**data/prize_lines.txt** - Lines said when prize is won

### 5. Create Sounds Directory

```bash
mkdir -p sounds
```

Add your sound files (WAV format recommended):
- `announcement.wav` (TTS pre-sound)
- `wheel_start.wav`
- `wheel_loop.wav`
- `wheel_win.wav`
- Other custom sound effects

## Usage

### Starting the Bot

```bash
python -m app.main
```

Or use the main entry point:

```bash
python app/main.py
```

The bot will:
1. Load configuration from `.env`
2. Initialize the SQLite database
3. Start the FastAPI web server
4. Connect to Joystick.tv via OAuth
5. Begin listening for chat events

### Accessing the Admin Dashboard

1. Open your browser to `http://localhost:8080/admin`
2. If you set an `ADMIN_TOKEN`, you'll need to authenticate
3. Navigate through tabs:
   - **Dashboard** - User stats and leaderboards
   - **Users** - Individual user management
   - **Transactions** - Points and XP history
   - **Batch Operations** - Bulk adjustments
   - **Settings** - Configuration management

### OAuth Setup

1. Register your application on Joystick.tv developer portal
2. Set the redirect URI to match your `JOYSTICK_REDIRECT_URI`
3. Save your Client ID and Client Secret to `.env`
4. Navigate to the OAuth flow in your browser to authorize
5. The bot will store access tokens in the database

## Bot Commands

Users can interact with Pixel through chat commands (configured in your redeem handlers):

- `!points` or `!balance` - Check point balance
- `!level` or `!rank` - Check XP level
- `!spin` - Spin the prize wheel (if enabled)
- `!leaderboard` or `!top` - Show top users
- Custom redeems configured in your Joystick.tv dashboard

## Architecture

```
Pixel/
├── app/
│   ├── admin/          # Admin dashboard & API endpoints
│   ├── core/           # Core bot functionality
│   │   ├── config.py       # Configuration management
│   │   ├── joystick.py     # Joystick.tv integration
│   │   ├── consumers.py    # Event handlers
│   │   ├── points.py       # Points system
│   │   ├── xp.py           # XP & leveling
│   │   ├── redeems.py      # Redeem handlers
│   │   ├── tts.py          # Text-to-speech
│   │   ├── wheel.py        # Prize wheel
│   │   ├── pixel.py        # AI chat integration
│   │   ├── models.py       # Database models
│   │   └── effects/        # Visual effects
│   └── main.py         # Application entry point
├── data/               # Configuration files
├── sounds/             # Audio files
├── tip-clicker-extension/  # Browser extension
├── requirements.txt    # Python dependencies
└── .env               # Environment configuration
```

## Development

### Database

Pixel uses SQLite with SQLAlchemy ORM. The database is automatically created on first run.

Key tables:
- `users` - User profiles, points, XP, levels
- `points_transactions` - Points history
- `xp_transactions` - XP history
- `oauth_installations` - Joystick.tv OAuth tokens

### Adding Custom Redeems

Edit `app/core/redeems.py` to add custom redeem handlers:

```python
redeem_handlers = {
    "custom_redeem_id": handle_custom_redeem,
}

async def handle_custom_redeem(event_data: dict):
    # Your custom logic here
    pass
```

### Extending the Bot

1. **New Event Handlers** - Add to `app/core/consumers.py`
2. **New Effects** - Create modules in `app/core/effects/`
3. **Admin Features** - Extend `app/admin/server.py`
4. **Database Models** - Modify `app/core/models.py`

## Troubleshooting

### Bot won't start
- Check `.env` configuration
- Verify Python version (3.10+)
- Ensure all dependencies installed: `pip install -r requirements.txt`

### OAuth connection fails
- Verify Joystick.tv credentials in `.env`
- Check redirect URI matches exactly
- Ensure bot has proper permissions

### TTS not working
- Verify sound files exist in `sounds/` directory
- Check file formats (WAV recommended)
- Review TTS settings in `.env`

### OBS integration issues
- Enable OBS WebSocket in OBS settings
- Verify port matches `OBS_WS_PORT`
- Check OBS WebSocket password

### Database errors
- Delete `pixel.db` and restart (loses data)
- Check file permissions
- Review SQLAlchemy logs

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is provided as-is for personal use. Check with the repository owner for licensing terms.

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing documentation in `/BATCH_OPERATIONS_INTEGRATION.md`
- Review configuration examples

## Changelog

### v2.1.0
- Added batch operations for points and XP
- Improved admin dashboard
- Enhanced Joystick.tv OAuth flow
- ActionCable WebSocket integration

### v2.0.0
- XP and leveling system
- Level rewards
- Enhanced user tracking

### v1.0.0
- Initial release
- Points system
- Basic redeems
- TTS integration
- Prize wheel

## Credits

Developed by [MaisieBae](https://github.com/MaisieBae) for the Joystick.tv streaming community.

---

**Note:** This bot is designed for Joystick.tv. It requires valid OAuth credentials and an active Joystick.tv account to function.

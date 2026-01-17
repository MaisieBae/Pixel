# Customization Guide

How to extend and customize Pixel Bot for your needs.

## Custom Redeems

### Creating a New Redeem

```python
from app.core.redeems import RedeemsService

with SessionLocal() as db:
    redeems = RedeemsService(db)
    redeems.upsert(
        key="dance",
        display_name="Make Streamer Dance",
        cost=500,
        enabled=True,
        cooldown_s=120
    )
```

### Handling the Redeem

```python
async def handle_dance_redeem(user: str):
    with SessionLocal() as db:
        redeems = RedeemsService(db)
        
        result = redeems.redeem(
            user_name=user,
            key="dance",
            queue_kind=None,
            payload={"user": user}
        )
        
        if result["ok"]:
            await trigger_osc_parameter("/avatar/parameters/Dance", True)
            await send_message(f"@{user} made the streamer dance!")
            await asyncio.sleep(10)
            await trigger_osc_parameter("/avatar/parameters/Dance", False)
```

## Custom Event Handlers

### New Event Type

```python
async def on_raid(raider: str, viewer_count: int):
    with SessionLocal() as db:
        points = PointsService(db)
        xp = XPService(db)
        
        user = points.ensure_user(raider)
        points.grant(user.id, viewer_count * 10, reason="raid")
        xp.adjust(raider, viewer_count * 5, reason="raid", source="event")
        
        await send_message(f"Thank you @{raider} for the raid!")
```

### Extending Existing Handlers

```python
original_on_tip = on_tip

async def on_tip(user: str, tokens: int):
    await original_on_tip(user, tokens)
    
    if tokens >= 1000:
        await obs.set_source_visibility("Gaming", "BigTipEffect", True)
        await asyncio.sleep(10)
        await obs.set_source_visibility("Gaming", "BigTipEffect", False)
```

## Custom Level Rewards

### Configuration File

**Location**: `./data/level_rewards.json`

```json
[
  {
    "level": 10,
    "points": 1000,
    "badge": "veteran",
    "announce": true,
    "tts": true,
    "message": "{user} is now a Veteran!"
  },
  {
    "level": 25,
    "points": 5000,
    "custom_action": "grant_vip",
    "announce": true
  }
]
```

### Custom Actions

```python
def apply_custom_rewards(db, user_id, user_name, level, rewards_path):
    reward = get_reward_for_level(level, rewards_path)
    
    if reward.get("custom_action") == "grant_vip":
        vip_service.add_vip(user_name)
    elif reward.get("custom_action") == "special_role":
        await assign_discord_role(user_name, reward["role_id"])
```

## Custom Prize Wheel Outcomes

### Adding New Prize Types

```json
[
  {
    "name": "VIP for 1 Hour",
    "weight": 5,
    "custom": true,
    "action": "temp_vip",
    "duration": 3600
  }
]
```

### Custom Prize Handler

```python
async def apply_prize(user_id, user_name, prize):
    if prize.get("custom"):
        action = prize.get("action")
        
        if action == "temp_vip":
            duration = prize.get("duration", 3600)
            await grant_temp_vip(user_name, duration)
            await send_message(f"@{user_name} is VIP for 1 hour!")
```

## Custom Chat Commands

### Command Framework

```python
class CommandHandler:
    def __init__(self):
        self.commands = {}
    
    def register(self, name: str, handler):
        self.commands[name] = handler
    
    async def handle(self, user: str, text: str):
        if not text.startswith("!"):
            return False
        
        parts = text[1:].split()
        command = parts[0].lower()
        args = parts[1:]
        
        if command in self.commands:
            await self.commands[command](user, args)
            return True
        return False

commands = CommandHandler()

@commands.register("points")
async def cmd_points(user: str, args: list):
    target = args[0] if args else user
    with SessionLocal() as db:
        points_svc = PointsService(db)
        u = points_svc.ensure_user(target)
        await send_message(f"@{target} has {u.points} points")
```

## Custom Integrations

### Discord Webhook

```python
import aiohttp

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."

async def send_discord_notification(message: str):
    async with aiohttp.ClientSession() as session:
        await session.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message}
        )

async def on_sub(user: str, months: int):
    # ... existing logic ...
    await send_discord_notification(f"🎉 {user} subscribed!")
```

### VRChat OSC

```python
from pythonosc import udp_client

osc_client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

async def trigger_osc_parameter(address: str, value):
    osc_client.send_message(address, value)

async def handle_emote_redeem(user: str, emote: str):
    await trigger_osc_parameter(f"/avatar/parameters/{emote}", True)
    await asyncio.sleep(5)
    await trigger_osc_parameter(f"/avatar/parameters/{emote}", False)
```

## Best Practices

### Organize Custom Code

```
app/
  custom/
    __init__.py
    commands.py
    redeems.py
    events.py
```

### Use Configuration

```ini
CUSTOM_FEATURE_ENABLED=true
CUSTOM_WEBHOOK_URL=https://...
```

### Document Changes

Create `CUSTOMIZATIONS.md`:

```markdown
# Custom Features

## Dance Redeem
- Cost: 500 points
- Triggers VRChat OSC
- 2 minute cooldown
```

## See Also

- [Redeems System](redeems.md)
- [Event Flow](event-flow.md)
- [Database Schema](database-schema.md)

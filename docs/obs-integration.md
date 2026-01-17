# OBS WebSocket Integration

Pixel Bot can control OBS Studio through the obs-websocket plugin for scene switching, source visibility, and recording control.

## Overview

The integration allows:
- Scene switching
- Source visibility control
- Recording start/stop
- Clip saving (replay buffer)
- Filter toggling
- Audio muting/unmuting

## Configuration

```ini
# OBS WebSocket Connection
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your-obs-password

# Enable OBS integration
OBS_ENABLED=true
```

## Setup

### Install obs-websocket

1. Download from [obs-websocket releases](https://github.com/obsproject/obs-websocket/releases)
2. Install plugin
3. Open OBS > Tools > WebSocket Server Settings
4. Enable WebSocket server
5. Set port (default: 4455)
6. Set password

### Configure Bot

Update `.env` with OBS credentials:

```ini
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=your-password-here
OBS_ENABLED=true
```

## Basic Usage

### Connection

```python
from app.core.obs import OBSClient

obs = OBSClient(settings)
await obs.connect()
```

### Scene Switching

```python
# Switch to specific scene
await obs.set_current_scene("Gaming")

# Get current scene
current = await obs.get_current_scene()
print(current)  # "Gaming"

# List all scenes
scenes = await obs.get_scene_list()
for scene in scenes:
    print(scene["sceneName"])
```

### Source Control

```python
# Show/hide source
await obs.set_source_visibility(
    scene="Gaming",
    source="Webcam",
    visible=True
)

# Toggle source
await obs.toggle_source_visibility(
    scene="Gaming",
    source="Overlay"
)
```

### Recording Control

```python
# Start recording
await obs.start_recording()

# Stop recording
await obs.stop_recording()

# Toggle recording
await obs.toggle_recording()

# Check status
status = await obs.get_recording_status()
print(status["outputActive"])  # True/False
```

### Replay Buffer (Clips)

```python
# Save replay buffer as clip
await obs.save_replay_buffer()

# Note: Replay buffer must be enabled in OBS
# Settings > Output > Replay Buffer
```

## Event-Triggered Actions

### Scene Switch on Sub

```python
async def on_sub(user: str, months: int):
    # Switch to celebration scene
    await obs.set_current_scene("Celebration")
    
    # Wait 10 seconds
    await asyncio.sleep(10)
    
    # Switch back
    await obs.set_current_scene("Gaming")
```

### Show Alert on Tip

```python
async def on_tip(user: str, tokens: int):
    if tokens >= 100:
        # Show big tip alert source
        await obs.set_source_visibility(
            scene="Gaming",
            source="BigTipAlert",
            visible=True
        )
        
        await asyncio.sleep(5)
        
        # Hide alert
        await obs.set_source_visibility(
            scene="Gaming",
            source="BigTipAlert",
            visible=False
        )
```

### Auto-Save Clips

```python
async def on_chat(user: str, text: str):
    if text == "!clip":
        # Check cooldown
        if not await check_clip_cooldown(user):
            await send_message(f"@{user} clip cooldown active")
            return
        
        # Save clip
        await obs.save_replay_buffer()
        await send_message(f"@{user} clip saved!")
        
        # Set cooldown
        await set_clip_cooldown(user, 60)  # 60 seconds
```

## Advanced Features

### Filter Control

```python
# Toggle filter on source
await obs.set_source_filter_enabled(
    source="Webcam",
    filter="Color Correction",
    enabled=True
)
```

### Audio Control

```python
# Mute/unmute source
await obs.set_input_mute(
    input="Desktop Audio",
    muted=True
)

# Set volume (0.0 to 1.0)
await obs.set_input_volume(
    input="Mic/Aux",
    volume=0.75
)
```

### Stream Control

```python
# Start streaming
await obs.start_stream()

# Stop streaming
await obs.stop_stream()

# Get stream status
status = await obs.get_stream_status()
print(status["outputActive"])
```

## Error Handling

### Connection Errors

```python
try:
    await obs.connect()
except Exception as e:
    print(f"OBS connection failed: {e}")
    # Bot continues without OBS features
```

### Command Errors

```python
try:
    await obs.set_current_scene("NonExistent")
except Exception as e:
    print(f"Scene switch failed: {e}")
    await send_message("Scene not found!")
```

### Auto-Reconnect

```python
while True:
    try:
        if not obs.is_connected():
            await obs.connect()
        # ... commands ...
    except Exception as e:
        print(f"OBS error: {e}")
        await asyncio.sleep(5)  # Wait before retry
```

## Integration Examples

### Scene Rotation

```python
scenes = ["Gaming", "Chatting", "BRB"]
current_index = 0

async def rotate_scene():
    global current_index
    current_index = (current_index + 1) % len(scenes)
    await obs.set_current_scene(scenes[current_index])

# Call every 30 minutes
scheduler.add_job(rotate_scene, "interval", minutes=30)
```

### Reward Redemptions

```python
# User redeems "Show Webcam"
async def handle_show_webcam_redeem(user: str):
    await obs.set_source_visibility(
        scene="Gaming",
        source="Webcam",
        visible=True
    )
    
    await send_message(f"@{user} activated webcam for 30 seconds!")
    
    await asyncio.sleep(30)
    
    await obs.set_source_visibility(
        scene="Gaming",
        source="Webcam",
        visible=False
    )
```

### Goal Tracking

```python
# Update progress bar based on tip total
tip_total = 0
tip_goal = 1000

async def on_tip(user: str, tokens: int):
    global tip_total
    tip_total += tokens
    
    # Calculate percentage
    progress = min(100, (tip_total / tip_goal) * 100)
    
    # Update OBS text source (requires custom implementation)
    await obs.set_text_source(
        source="TipGoal",
        text=f"Tip Goal: {tip_total}/{tip_goal} ({progress:.0f}%)"
    )
```

## Best Practices

### Check Connection Before Commands

```python
if obs.is_connected():
    await obs.set_current_scene("Gaming")
else:
    print("OBS not connected")
```

### Use Try-Except for Reliability

```python
try:
    await obs.set_current_scene(scene)
except Exception:
    # Fail silently, don't crash bot
    pass
```

### Verify Scene/Source Names

```python
scenes = await obs.get_scene_list()
scene_names = [s["sceneName"] for s in scenes]

if "Gaming" in scene_names:
    await obs.set_current_scene("Gaming")
else:
    print("Scene 'Gaming' not found")
```

## Troubleshooting

### Can't connect to OBS

1. Verify obs-websocket installed
2. Check WebSocket server enabled in OBS
3. Verify port matches (default: 4455)
4. Check password is correct
5. Ensure OBS is running

### Scene/source not found

1. Check exact name (case-sensitive)
2. List all scenes/sources to verify
3. Check scene contains the source

### Replay buffer not working

1. Enable in OBS: Settings > Output > Replay Buffer
2. Set buffer duration
3. Start replay buffer in OBS
4. Then call `save_replay_buffer()`

## See Also

- [Event Flow](event-flow.md) - Event-triggered OBS actions
- [Redeems System](redeems.md) - OBS control via redeems
- [Configuration](configuration.md) - OBS settings

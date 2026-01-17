# Text-to-Speech (TTS) System

The TTS system converts text messages into speech audio, allowing viewers to have their messages read aloud on stream.

## Overview

TTS operates as a queue-based system where messages are processed sequentially with optional pre-sounds and username prefixes.

## Architecture

### Service Class: `TTSService`

**Location**: `app/core/tts.py`

```python
class TTSService:
    def pending_count() -> int
    async def next_plain() -> str
```

### Queue Model

TTS messages are stored in the `queue_items` table:

```python
QueueItem(
    kind="tts",
    status="pending",  # -> "running" -> "done"
    payload_json={
        "user": "alice",
        "message": "Hello world",
        "prefix": True,
        "source": "redeem"
    }
)
```

## Configuration

### Settings

```ini
# TTS Pre-Roll Sound
TTS_PRE_SOUND=announcement.wav

# Maximum TTS Queue Size
TTS_QUEUE_MAX=5

# Per-User Cooldown
TTS_COOLDOWN_SECONDS=10

# Prefix username to message
TTS_PREFIX_USERNAME=true

# Delay between pre-sound and speech (milliseconds)
TTS_PRE_DELAY_MS=1200
```

### Cost

TTS cost is configured in the redeems system:

```python
redeem = redeems.get("tts")
print(redeem.cost)  # Default: 25 points
```

## TTS Flow

### User-Initiated TTS

```
1. User redeems TTS for 25 points with message "Hello world"
2. RedeemsService validates:
   - User has 25+ points
   - Not on TTS cooldown
   - Queue not full (< 5 pending)
3. Points deducted (25)
4. QueueItem created:
   {
     "kind": "tts",
     "status": "pending",
     "payload_json": {
       "user": "alice",
       "message": "Hello world",
       "prefix": true,
       "source": "redeem"
     }
   }
5. Cooldown set (10 seconds)
6. Confirmation sent to chat
```

### TTS Processing (Two-Stage)

**Stage 1: Priming**

```python
1. Queue processor calls next_plain()
2. Finds first "pending" item
3. Changes status to "running"
4. Plays pre-sound (announcement.wav)
5. Records primed_at timestamp
6. Returns empty string (not ready yet)
```

**Stage 2: Speaking**

```python
1. Queue processor calls next_plain() again
2. Finds "running" item
3. Checks if delay elapsed (primed_at + 1200ms)
4. If yes:
   - Builds text: "Alice said: Hello world"
   - Marks item as "done"
   - Returns text for TTS engine
5. TTS engine speaks text
6. Process repeats for next message
```

### Why Two-Stage?

The two-stage process allows:
- Pre-sound to fully play before speech starts
- Smooth transitions between messages
- Prevents audio overlap
- Gives viewers auditory cue that TTS is coming

## Text Building

### Username Prefixing

If `TTS_PREFIX_USERNAME=true`:

```python
Input:  {"user": "alice", "message": "Hello"}
Output: "Alice said: Hello"
```

If `TTS_PREFIX_USERNAME=false`:

```python
Input:  {"user": "alice", "message": "Hello"}
Output: "Hello"
```

### Text Sanitization

For AI-generated messages (source="pixel"):

```python
from app.core.text import sanitize_tts_text

# Removes problematic characters, URLs, etc.
sanitized = sanitize_tts_text(raw_message)
```

**Location**: `app/core/text.py`

## Queue Management

### Checking Queue Status

```python
count = tts_service.pending_count()
if count >= settings.TTS_QUEUE_MAX:
    return {"error": "TTS queue is full"}
```

### Queue Limit

Default limit is 5 pending messages. This prevents:
- Queue flooding
- Long wait times
- Stream disruption

### Manual Queue Inspection

```python
from app.core.models import QueueItem
from sqlalchemy import select

pending = db.scalars(
    select(QueueItem).where(
        QueueItem.kind == "tts",
        QueueItem.status == "pending"
    ).order_by(QueueItem.id.asc())
)

for item in pending:
    payload = item.payload_json
    print(f"{payload['user']}: {payload['message']}")
```

## TTS Sources

### 1. Redeem (User-Triggered)

```python
payload = {
    "user": "alice",
    "message": "Hello world",
    "prefix": True,
    "source": "redeem"
}
```

Most common source. User spends points for TTS.

### 2. Level-Up Reward

```python
payload = {
    "user": "bob",
    "message": "Bob reached level 10!",
    "prefix": False,  # Already mentions username
    "source": "level"
}
```

Automatic TTS when user levels up (if configured in level_rewards.json).

### 3. AI Response

```python
payload = {
    "user": "pixel",
    "message": "That's a great question! Here's what I think...",
    "prefix": False,
    "source": "pixel"
}
```

AI-generated responses are sanitized before speaking.

### 4. Admin/System

```python
payload = {
    "user": "system",
    "message": "Stream starting in 5 minutes!",
    "prefix": False,
    "source": "admin"
}
```

Manual announcements or automated alerts.

## Sound Effects

### Pre-Sound

**Purpose**: Audio cue that TTS is about to speak

**Requirements**:
- File must exist in `sounds/` directory
- WAV format recommended
- Short duration (0.5-2 seconds)

**Configuration**:
```ini
TTS_PRE_SOUND=announcement.wav
```

**Common Pre-Sounds**:
- `announcement.wav` - Attention chime
- `ding.wav` - Simple notification
- `whoosh.wav` - Transition sound
- `fanfare.wav` - Celebratory intro

### Custom Pre-Sounds per Source

To use different pre-sounds based on source:

```python
# Modify TTSService._prime_tts()
async def _prime_tts(self, item: QueueItem):
    payload = item.payload_json
    source = payload.get("source", "redeem")
    
    if source == "level":
        pre_sound = "level_up.wav"
    elif source == "pixel":
        pre_sound = "ai_beep.wav"
    else:
        pre_sound = self.settings.TTS_PRE_SOUND
    
    await play_sfx(self.bus, pre_sound)
```

## Cooldowns

### Per-User Cooldown

```python
# User redeems TTS at 12:00:00
# Cooldown set: 10 seconds
# User cannot redeem TTS again until 12:00:10
# Other users can still redeem
```

### Override Cooldown

For special cases (admin commands, level rewards):

```python
result = redeems.redeem(
    user_name="alice",
    key="tts",
    cooldown_s=0,  # No cooldown
    queue_kind="tts",
    payload={...}
)
```

### Queue as Rate Limit

The queue itself provides rate limiting:
- Max 5 pending messages
- Sequential processing (1 at a time)
- Natural pacing from pre-sound delays

## Integration Examples

### Chat Command TTS

```python
async def on_chat(user: str, text: str):
    if text.startswith("!tts "):
        message = text[5:]  # Remove "!tts " prefix
        
        with SessionLocal() as db:
            redeems = RedeemsService(db)
            tts = TTSService(db, settings, bus)
            
            # Check queue
            if tts.pending_count() >= settings.TTS_QUEUE_MAX:
                await send_message(f"@{user} TTS queue is full!")
                return
            
            # Attempt redeem
            result = redeems.redeem(
                user_name=user,
                key="tts",
                cooldown_s=None,
                queue_kind="tts",
                payload={
                    "user": user,
                    "message": message,
                    "prefix": True,
                    "source": "redeem"
                }
            )
            
            if result["ok"]:
                await send_message(f"@{user} TTS queued!")
            else:
                await send_message(f"@{user} {result['error']}")
```

### Level-Up TTS

```python
# In level_rewards.py
def apply_level_rewards(db, user_id, user_name, new_level, rewards_path):
    # ... existing code ...
    
    if reward.get("tts"):
        msg = reward["message"].replace("{user}", user_name)
        db.add(QueueItem(
            kind="tts",
            status="pending",
            payload_json={
                "user": user_name,
                "message": msg,
                "prefix": False,
                "source": "level"
            }
        ))
```

### AI Response TTS

```python
async def handle_pixel_redeem(user: str, question: str):
    # Get AI response
    response = await call_perplexity(settings, question)
    
    # Queue TTS
    with SessionLocal() as db:
        db.add(QueueItem(
            kind="tts",
            status="pending",
            payload_json={
                "user": "pixel",
                "message": response,
                "prefix": False,
                "source": "pixel"
            }
        ))
        db.commit()
```

## TTS Engine Integration

Pixel Bot provides the text; your streaming software handles actual speech:

### Option 1: Browser Source

Create an overlay that:
1. Polls `/admin/api/tts/next` endpoint
2. Uses Web Speech API to speak text
3. Returns result to mark complete

### Option 2: OBS Plugin

Use obs-websocket to:
1. Monitor TTS queue
2. Trigger external TTS program
3. Play audio as media source

### Option 3: External Service

Integrate with TTS services:
- Google Cloud Text-to-Speech
- Amazon Polly
- Microsoft Azure Speech
- ElevenLabs

**Example Integration**:

```python
import azure.cognitiveservices.speech as speechsdk

async def speak_with_azure(text: str):
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_REGION
    )
    audio_config = speechsdk.audio.AudioOutputConfig(
        use_default_speaker=True
    )
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    synthesizer.speak_text_async(text).get()
```

## Troubleshooting

### TTS not speaking

1. Check queue: `tts_service.pending_count()`
2. Verify TTS engine is running
3. Check pre-sound file exists
4. Review queue processor logs
5. Ensure overlay/integration is active

### Messages out of order

Queue should be FIFO (first-in, first-out):

```python
# Verify order
pending = db.scalars(
    select(QueueItem)
    .where(QueueItem.kind == "tts", QueueItem.status == "pending")
    .order_by(QueueItem.id.asc())
)
```

### Queue stuck

If items stuck in "running" status:

```python
# Reset stuck items
stuck = db.scalars(
    select(QueueItem).where(
        QueueItem.kind == "tts",
        QueueItem.status == "running",
        QueueItem.started_at < (datetime.utcnow() - timedelta(minutes=5))
    )
)
for item in stuck:
    item.status = "failed"
db.commit()
```

### Pre-sound too quiet/loud

Adjust audio levels:
1. Edit WAV file volume in audio editor
2. Or implement volume normalization in code

## Best Practices

### Cost and Cooldown

- **Cost**: 25-50 points (low enough to encourage use)
- **Cooldown**: 10-30 seconds (prevents spam)
- **Queue limit**: 3-5 messages (keeps wait times reasonable)

### Message Filtering

**Recommended filters**:
- Maximum length (200-500 characters)
- Profanity filter (optional)
- URL removal
- Special character sanitization

**Implementation**:

```python
def filter_tts_message(text: str) -> str:
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    
    # Limit length
    text = text[:500]
    
    # Remove excessive punctuation
    text = re.sub(r'[!?]{3,}', '!!!', text)
    
    return text.strip()
```

### Queue Monitoring

Alert streamer when queue gets full:

```python
if tts_service.pending_count() >= settings.TTS_QUEUE_MAX:
    await send_message("⚠️ TTS queue is full!")
```

## See Also

- [Redeems System](redeems.md) - TTS as a redeem
- [Event Flow](event-flow.md#queue-processing) - Queue mechanics
- [Configuration](configuration.md) - TTS settings reference

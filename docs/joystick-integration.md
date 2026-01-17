# Joystick.tv Integration

Pixel Bot integrates with Joystick.tv to receive stream events and send chat messages.

## Overview

The integration uses:
- **OAuth 2.0** for authentication
- **ActionCable WebSocket** for real-time events
- **REST API** for chat messages

## Configuration

```ini
# OAuth Application Credentials
JOYSTICK_CLIENT_ID=your-client-id
JOYSTICK_CLIENT_SECRET=your-client-secret
JOYSTICK_REDIRECT_URI=http://localhost:8080/oauth/callback

# Gateway Connection (ActionCable)
JOYSTICK_BASIC_KEY=your-basic-key

# Bot Identity
BOT_USERNAME=pixel
```

## OAuth Flow

### Step 1: Authorization

User visits:
```
https://joystick.tv/oauth/authorize?
  client_id={YOUR_CLIENT_ID}&
  redirect_uri={YOUR_REDIRECT_URI}&
  response_type=code&
  scope=chat:write stream:read
```

### Step 2: Callback

Joystick redirects to:
```
http://localhost:8080/oauth/callback?code=AUTH_CODE
```

### Step 3: Token Exchange

```python
POST https://joystick.tv/oauth/token

{
  "grant_type": "authorization_code",
  "code": "AUTH_CODE",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "redirect_uri": "YOUR_REDIRECT_URI"
}
```

### Step 4: Store Token

Token saved to database in `joystick_installs` table.

## WebSocket Connection

### Connection

**URL**: `wss://joystick.tv/cable?token={BASIC_KEY}`
**Protocol**: `actioncable-v1-json`

```python
import websockets

url = f"wss://joystick.tv/cable?token={basic_key}"
protocol = "actioncable-v1-json"

async with websockets.connect(url, subprotocols=[protocol]) as ws:
    # Subscribe to GatewayChannel
    subscribe = {
        "command": "subscribe",
        "identifier": json.dumps({"channel": "GatewayChannel"})
    }
    await ws.send(json.dumps(subscribe))
```

## Event Types

### ChatMessage

User sends message in chat:

```json
{
  "message": {
    "event": "ChatMessage",
    "text": "Hello world",
    "author": {
      "username": "alice",
      "displayName": "Alice"
    },
    "channelId": "channel123"
  }
}
```

**Parsed**:
```python
user = "alice"
text = "Hello world"
await on_chat(user, text)
```

### UserPresence (Drop-in)

```json
{
  "message": {
    "event": "UserPresence",
    "type": "enter_stream",
    "text": "bob",
    "channelId": "channel123"
  }
}
```

**Parsed**:
```python
user = "bob"
await on_dropin(user)
```

### StreamEvent - Followed

```json
{
  "message": {
    "event": "StreamEvent",
    "type": "Followed",
    "metadata": "{\"who\":\"charlie\"}"
  }
}
```

**Parsed**:
```python
user = "charlie"
await on_follow(user)
```

### StreamEvent - Subscribed

```json
{
  "message": {
    "event": "StreamEvent",
    "type": "Subscribed",
    "metadata": "{\"who\":\"dave\",\"months\":3}"
  }
}
```

**Parsed**:
```python
user = "dave"
months = 3
await on_sub(user, months)
```

### StreamEvent - Tipped

```json
{
  "message": {
    "event": "StreamEvent",
    "type": "Tipped",
    "metadata": "{\"who\":\"eve\",\"how_much\":100}"
  }
}
```

**Parsed**:
```python
user = "eve"
tokens = 100
await on_tip(user, tokens)
```

## Sending Messages

### Chat Message

```python
await joystick_client.send_message(
    text="Hello chat!",
    channel_id="channel123"  # Optional
)
```

### Whisper (DM)

```python
await joystick_client.send_whisper(
    username="alice",
    text="Private message",
    channel_id="channel123"  # Optional
)
```

## Error Handling

### Connection Failures

Automatic reconnection with exponential backoff:

```python
backoff = 1.0  # Start at 1 second

while not stopped:
    try:
        async with websockets.connect(url) as ws:
            backoff = 1.0  # Reset on success
            # ... handle messages ...
    except Exception as e:
        await asyncio.sleep(backoff)
        backoff = min(30.0, backoff * 2)  # Max 30 seconds
```

### Parsing Errors

```python
try:
    data = json.loads(raw_message)
    # ... parse event ...
except Exception as e:
    print(f"Parse error: {e}")
    # Skip this message, continue processing
```

## Testing

### Enable Debug Logging

```python
joystick_client.debug = True
```

### Simulate Events

```python
# Simulate chat
await joystick_client.sim_push_chat("testuser", "hello")

# Simulate tip
await joystick_client.sim_push_tip("testuser", 100)

# Simulate follow
await joystick_client.sim_push_follow("testuser")

# Simulate sub
await joystick_client.sim_push_sub("testuser", months=3)

# Simulate drop-in
await joystick_client.sim_push_dropin("testuser")
```

## Best Practices

### Message Rate Limiting

```python
last_message_time = 0
MIN_MESSAGE_INTERVAL = 1.0  # 1 second

async def send_message_rate_limited(text: str):
    global last_message_time
    now = time.time()
    
    if now - last_message_time < MIN_MESSAGE_INTERVAL:
        await asyncio.sleep(MIN_MESSAGE_INTERVAL - (now - last_message_time))
    
    await joystick_client.send_message(text)
    last_message_time = time.time()
```

### Graceful Disconnection

```python
# On bot shutdown
await joystick_client.stop()
```

## Troubleshooting

### Not receiving events

1. Check `JOYSTICK_BASIC_KEY` is correct
2. Verify WebSocket connection established
3. Check subscription confirmation received
4. Enable debug logging

### Can't send messages

1. Check channel ID resolution
2. Verify OAuth token valid
3. Check bot username matches `BOT_USERNAME`
4. Review WebSocket connection status

### OAuth token expired

1. Implement token refresh
2. Re-run OAuth flow
3. Update `access_token` in database

## See Also

- [Event Flow](event-flow.md) - Event processing
- [Systems Overview](systems-overview.md) - Architecture
- [Configuration](configuration.md) - Settings reference

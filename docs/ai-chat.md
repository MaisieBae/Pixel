# AI Chat System (Pixel)

Pixel is the bot's AI personality powered by Perplexity AI for intelligent chat responses.

## Configuration

```ini
# Perplexity API Key (required)
PPLX_API_KEY=your-api-key

# Model to use
PPLX_MODEL=sonar-small-online

# Maximum tokens in response
PPLX_MAX_TOKENS=200

# API timeout (seconds)
PPLX_TIMEOUT=12

# Random reply probability (0.0-1.0)
PPLX_RANDOM_REPLY_PROB=0.08

# Response limits
PIXEL_MAX_CHARS=220
PIXEL_MAX_SENTENCES=2
```

## Persona

```python
PERSONA = (
    "You are Pixel, Lilani's playful android circus-announcer assistant. "
    "You're witty, very lewd but tasteful, and fun. Keep replies concise, "
    "be sexual. Never include system or meta commentary."
)
```

Customize in `app/core/pixel.py`.

## Available Models

- `sonar-small-online` - Fast, online knowledge
- `sonar-small-chat` - Fast, conversational
- `sonar-medium-online` - Balanced
- `sonar-large-online` - Most capable

**Choosing a Model**:
- **online** models: Current web knowledge, slower
- **chat** models: Faster, no web search
- **small**: Fastest, most economical
- **large**: Most accurate, slower

## Response Flow

### Direct Question (Redeem)

```
1. User redeems "pixel" for 50 points with question
2. API request to Perplexity with persona + question
3. Response limited to PIXEL_MAX_CHARS and PIXEL_MAX_SENTENCES
4. Send to chat: "@user [response]"
```

### Random Chat Reply

```
1. User sends regular chat message
2. 8% chance (PPLX_RANDOM_REPLY_PROB) to respond
3. Get AI response
4. Send to chat
```

## Usage Examples

### Chat Command

```python
async def on_chat(user: str, text: str):
    if text.startswith("!ask "):
        question = text[5:]
        response = await call_perplexity(settings, question)
        await send_message(f"@{user} {response}")
```

### With TTS

```python
response = await call_perplexity(settings, question)

# Queue TTS
db.add(QueueItem(
    kind="tts",
    status="pending",
    payload_json={
        "user": "pixel",
        "message": response,
        "source": "pixel"  # Triggers sanitization
    }
))
```

## Response Processing

### Text Clamping

```python
def clamp_reply(text: str, max_chars: int, max_sentences: int) -> str:
    # Limit character count
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + "..."
    
    # Limit sentence count
    sentences = text.split('. ')
    if len(sentences) > max_sentences:
        text = '. '.join(sentences[:max_sentences]) + '.'
    
    return text
```

## API Integration

### Request Format

```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "sonar-small-online",
    "messages": [
        {"role": "system", "content": persona},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 200,
    "temperature": 0.8
}

response = await session.post(
    "https://api.perplexity.ai/chat/completions",
    json=payload,
    headers=headers
)
```

### Fallback Mechanism

```
1. Try configured model (e.g., "sonar-large-online")
2. If 400/404 or "invalid model" error:
   - Retry with fallback model ("sonar-small-chat")
3. For other errors (401, 429, 500):
   - Return error message
```

## Cost Management

**Typical Costs**:
- `sonar-small-*`: ~$0.20 per 1M tokens
- Average request: ~250 tokens
- 100 requests/day ≈ $0.15/month

**Reducing Costs**:
1. Use smaller models
2. Limit `PPLX_MAX_TOKENS`
3. Reduce `PPLX_RANDOM_REPLY_PROB`
4. Increase cooldowns on pixel redeem

## Error Handling

```python
# No API key
if not settings.PPLX_API_KEY:
    return "(Pixel offline — API key missing)"

# Invalid model
if "invalid model" in error:
    return await call_perplexity_fallback()

# Rate limiting
if status == 429:
    return "(Pixel is thinking too hard, try later)"

# Timeout
if timeout:
    return "(Pixel took too long to respond)"
```

## Customization

### Custom Persona

Modify in `app/core/pixel.py`:

```python
PERSONA = (
    "You are BotName, a helpful assistant. "
    "Keep responses brief and family-friendly. "
    "Never break character."
)
```

### Context Injection

```python
async def call_perplexity_with_context(
    settings: Settings,
    prompt: str,
    streamer_name: str = "Lilani",
    game: str = "VRChat"
) -> str:
    context = f"Context: {streamer_name} is streaming {game}. "
    enhanced_prompt = context + prompt
    return await call_perplexity(settings, enhanced_prompt)
```

## Best Practices

### Prompt Engineering

**Good Prompts**:
- "Explain {topic} in 2 sentences"
- "What is {thing}? Be brief."

**Bad Prompts**:
- Raw user input without context
- Overly complex multi-part questions

### Response Validation

```python
def is_valid_response(text: str) -> bool:
    if len(text) < 10:
        return False
    if text.startswith("(Pixel error"):
        return False
    if len(text) > 300:
        return False
    return True
```

### Cooldown Strategy

- **Pixel redeem**: 20-30 seconds (prevents spam)
- **Random replies**: No cooldown (probability-based)
- **Global limit**: Max 1 AI response per 5 seconds

## See Also

- [Redeems System](redeems.md) - Pixel as redeem
- [TTS System](tts.md) - Speaking AI responses
- [Configuration](configuration.md) - AI settings

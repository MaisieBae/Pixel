from __future__ import annotations
import re

# Pre-compiled patterns
_CITATION = re.compile(r"\[\s*\d+(?:\s*[-,]\s*\d+)*\s*\]")            # [2], [2-4], [2, 4]
_CHAINED = re.compile(r"(?:\[\s*\d+\s*\])+")                              # [2][4]
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^\)]+\)")                   # [text](url)
_URL = re.compile(r"https?://\S+")
_STARS = re.compile(r"\*+")
_BACKTICKS = re.compile(r"`+")
_BULLET_LINE_START = re.compile(r"^\s*[-•]\s*", re.M)                       # leading bullets per line
_BULLET_NEWLINE = re.compile(r"\n\s*[-•]\s*")                              # bullet mid-paragraph → ;
_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

def sanitize_tts_text(text: str) -> str:
    s = text or ""
    # Strip markdown links to plain text
    s = _MARKDOWN_LINK.sub(r"\1", s)
    # Remove raw URLs
    s = _URL.sub("", s)
    # Remove citations like [2], [2-4], chained [2][4]
    s = _CITATION.sub("", s)
    s = _CHAINED.sub("", s)
    # Remove emphasis markers and code ticks
    s = _STARS.sub("", s)
    s = _BACKTICKS.sub("", s)
    # Tidy bullets → read naturally
    s = _BULLET_LINE_START.sub("", s)
    s = _BULLET_NEWLINE.sub("; ", s)
    # Collapse excessive whitespace/newlines
    s = _WS.sub(" ", s).strip()
    return s

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def clamp_reply(text: str, max_chars: int, max_sentences: int) -> str:
    s = (text or "").strip()
    if not s:
        return s
    # Sentence clamp first
    if max_sentences and max_sentences > 0:
        parts = _SENT_SPLIT.split(s)
        if len(parts) > max_sentences:
            s = " ".join(parts[:max_sentences])
    # Char clamp next
    if max_chars and max_chars > 0 and len(s) > max_chars:
        s = s[: max(max_chars - 1, 1)].rstrip()
        # Don’t end mid‑word if possible
        last_space = s.rfind(" ")
        if last_space > 40:  # keep some content even if no spaces
            s = s[:last_space]
        s += "…"
    return s
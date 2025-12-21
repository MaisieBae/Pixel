from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Signal:
    name: str
    user: Optional[str] = None
    source: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class BaseSignalHandler:
    async def handle(self, signal: Signal) -> None:
        raise NotImplementedError

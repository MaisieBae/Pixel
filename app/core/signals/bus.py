import asyncio
from typing import List
from .base import Signal, BaseSignalHandler

class SignalBus:
    def __init__(self):
        self._handlers: List[BaseSignalHandler] = []

    def register(self, handler: BaseSignalHandler) -> None:
        self._handlers.append(handler)

    def emit(self, signal: Signal) -> None:
        for handler in self._handlers:
            asyncio.create_task(handler.handle(signal))

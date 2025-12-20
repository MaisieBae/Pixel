from __future__ import annotations
import socket
import struct
from dataclasses import dataclass
from typing import Any, Iterable

from app.core.config import Settings


def _pad4(b: bytes) -> bytes:
    # OSC strings/blobs are padded with zero bytes to a 4-byte boundary
    pad = (-len(b)) % 4
    return b + (b"\x00" * pad)


def _osc_str(s: str) -> bytes:
    return _pad4(s.encode("utf-8") + b"\x00")


@dataclass
class OscMessage:
    address: str
    type: str  # 'int'|'float'|'string'|'bool'
    value: Any = None  # for bool, value should be True/False


class OSCService:
    """
    Minimal OSC sender for VRChat (UDP).
    Supports: int32, float32, string, bool (T/F tags).

    VRChat listens by default on 127.0.0.1:9000 for incoming OSC messages.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enabled(self) -> bool:
        return bool(getattr(self.settings, "VRC_OSC_ENABLED", False))

    def _target(self) -> tuple[str, int]:
        host = str(getattr(self.settings, "VRC_OSC_HOST", "127.0.0.1")).strip() or "127.0.0.1"
        port = int(getattr(self.settings, "VRC_OSC_PORT", 9000) or 9000)
        return host, port

    def send(self, address: str, type_: str, value: Any = None) -> None:
        if not self.enabled():
            return
        msg = OscMessage(address=address, type=type_, value=value)
        self.send_many([msg])

    def send_many(self, messages: Iterable[OscMessage]) -> None:
        if not self.enabled():
            return
        host, port = self._target()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for m in messages:
                pkt = build_osc_packet(m.address, m.type, m.value)
                sock.sendto(pkt, (host, port))
        finally:
            try:
                sock.close()
            except Exception:
                pass


def build_osc_packet(address: str, type_: str, value: Any) -> bytes:
    addr = (address or "").strip()
    if not addr.startswith("/"):
        raise ValueError("OSC address must start with '/'")
    t = (type_ or "").strip().lower()

    # Build type tags and arguments
    if t in ("int", "i", "int32"):
        tags = ",i"
        args = struct.pack(">i", int(value))
    elif t in ("float", "f", "float32"):
        tags = ",f"
        args = struct.pack(">f", float(value))
    elif t in ("string", "s", "str"):
        tags = ",s"
        args = _osc_str(str(value))
    elif t in ("bool", "b", "boolean"):
        # OSC bool uses 'T' or 'F' with no argument payload
        v = bool(value)
        tags = ",T" if v else ",F"
        args = b""
    else:
        raise ValueError(f"Unsupported OSC type: {type_}")

    return _osc_str(addr) + _osc_str(tags) + args

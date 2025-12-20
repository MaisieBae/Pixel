from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class BackupInfo:
    name: str
    path: Path
    created_at_utc: str


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text_file(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text or "", encoding="utf-8")


def make_backup(src: Path, backups_dir: Path, prefix: str) -> BackupInfo:
    ensure_dir(backups_dir)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name = f"{prefix}_{ts}.bak"
    dst = backups_dir / name
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    else:
        dst.write_text("", encoding="utf-8")
    return BackupInfo(name=name, path=dst, created_at_utc=datetime.utcnow().isoformat() + "Z")


def list_backups(backups_dir: Path, prefix: str) -> list[BackupInfo]:
    if not backups_dir.exists():
        return []
    out: list[BackupInfo] = []
    for p in sorted(backups_dir.glob(f"{prefix}_*.bak"), reverse=True):
        out.append(BackupInfo(name=p.name, path=p, created_at_utc=datetime.utcfromtimestamp(p.stat().st_mtime).isoformat() + "Z"))
    return out

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class BackupInfo:
    name: str
    path: Path
    created_at: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def write_text_with_backup(
    path: Path,
    new_text: str,
    *,
    backup_dir: Path,
    prefix: str,
    keep: int = 25,
) -> BackupInfo | None:
    """Write a text file, backing up the previous contents.

    Backups are plain text files saved to backup_dir with a timestamped name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    prev = read_text(path) if path.exists() else ""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{prefix}_{ts}.bak.txt"
    # Always write a backup, even if prev is empty; this makes restore predictable.
    try:
        backup_path.write_text(prev, encoding="utf-8")
    except Exception:
        backup_path = None

    path.write_text(new_text, encoding="utf-8")

    # GC old backups
    try:
        backups = sorted(backup_dir.glob(f"{prefix}_*.bak.txt"), key=lambda p: p.name, reverse=True)
        for p in backups[keep:]:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

    if backup_path is None:
        return None
    return BackupInfo(name=backup_path.name, path=backup_path, created_at=ts)


def list_backups(backup_dir: Path, prefix: str, limit: int = 25) -> list[BackupInfo]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    out: list[BackupInfo] = []
    backups = sorted(backup_dir.glob(f"{prefix}_*.bak.txt"), key=lambda p: p.name, reverse=True)
    for p in backups[: max(1, int(limit))]:
        # parse timestamp
        ts = ""
        try:
            stem = p.name.replace(".bak.txt", "")
            ts = stem.split("_", maxsplit=1)[1] if "_" in stem else ""
        except Exception:
            ts = ""
        out.append(BackupInfo(name=p.name, path=p, created_at=ts))
    return out


def restore_backup(path: Path, backup_file: Path) -> None:
    """Restore a file from a backup file."""
    text = read_text(backup_file)
    path.write_text(text, encoding="utf-8")

"""
Automated Database Backup Utility:
- Creates timestamped copies of data/trucklead.db (including WAL/SHM if present) in backups/
- Computes and logs SHA-256 integrity hashes
- Retains only the most recent N (default 10) automated backups to prevent disk bloat
- Intended to be invoked before any migration, maintenance, or data pipeline execution
"""
import os
import glob
import shutil
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
BACKUP_DIR = ROOT_DIR / "backups"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def backup_database(
    db_path: Path = DATA_DIR / "trucklead.db",
    backup_dir: Path = BACKUP_DIR,
    max_backups: int = 10,
    prefix: str = "trucklead"
) -> Path:
    """Creates a timestamped backup and rotates older backups to keep the last max_backups."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Source database not found at {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_path = backup_dir / f"{prefix}_{timestamp}.db"

    # Copy primary DB
    shutil.copy2(db_path, dest_path)
    sha256 = compute_sha256(dest_path)
    size = dest_path.stat().st_size
    print(f"[BACKUP] Created {dest_path.name} ({size:,} bytes) | SHA-256: {sha256}")

    # Copy WAL and SHM if present
    wal_path = Path(str(db_path) + "-wal")
    if wal_path.is_file():
        shutil.copy2(wal_path, Path(str(dest_path) + "-wal"))
        print(f"[BACKUP] Copied WAL file {wal_path.name}")

    shm_path = Path(str(db_path) + "-shm")
    if shm_path.is_file():
        shutil.copy2(shm_path, Path(str(dest_path) + "-shm"))
        print(f"[BACKUP] Copied SHM file {shm_path.name}")

    # Rotate older automated backups beyond max_backups
    # Strict regex pattern: ONLY trucklead_YYYYMMDD_HHMMSS.db
    # Explicitly excludes before_restore, pre_cleanup, bak_, or any manual tags
    import re
    backup_files = [p for p in backup_dir.glob("trucklead_*.db") if p.is_file()]
    strictly_automated = []
    for p in backup_files:
        name = p.name
        if any(protected in name for protected in ["before_restore", "pre_cleanup", "bak_"]):
            continue
        if re.match(r"^trucklead_\d{8}_\d{6}\.db$", name):
            strictly_automated.append(p)

    strictly_automated.sort(key=lambda x: x.name)
    if len(strictly_automated) > max_backups:
        to_delete = strictly_automated[:-max_backups]
        for b_path in to_delete:
            try:
                b_path.unlink()
                wal = b_path.with_name(b_path.name + "-wal")
                shm = b_path.with_name(b_path.name + "-shm")
                if wal.exists(): wal.unlink()
                if shm.exists(): shm.unlink()
                print(f"[BACKUP] Rotated old backup: {b_path.name}")
            except Exception as e:
                print(f"[BACKUP] Warning deleting {b_path.name}: {e}")

    return dest_path


if __name__ == "__main__":
    backup_database()


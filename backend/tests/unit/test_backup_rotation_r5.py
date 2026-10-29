import pytest
from pathlib import Path
from scripts.maintenance.backup_db import backup_database


def test_backup_rotation_strict_naming_and_preservation(tmp_path):
    """
    R5: Verifies that backup rotation strictly deletes only files matching
    trucklead_YYYYMMDD_HHMMSS.db and NEVER touches files containing
    'before_restore', 'pre_cleanup', 'bak_', or manual tags.
    """
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    dummy_db = tmp_path / "dummy_trucklead.db"
    dummy_db.write_text("DUMMY DB CONTENT")

    # 1. Create protected files
    protected_names = [
        "trucklead_20261029_205450_before_restore.db",
        "trucklead_backup_pre_cleanup.db",
        "trucklead.db.bak_stepA",
        "trucklead.db.bak_stepE",
        "trucklead_manual_export.db"
    ]
    for name in protected_names:
        (backup_dir / name).write_text("PROTECTED")

    # 2. Create 12 automated backups with valid timestamp format
    automated_names = []
    for day in range(1, 13):
        ts_name = f"trucklead_202610{day:02d}_120000.db"
        (backup_dir / ts_name).write_text(f"AUTOMATED {day}")
        automated_names.append(ts_name)

    # 3. Run backup with max_backups = 10
    new_backup = backup_database(db_path=dummy_db, backup_dir=backup_dir, max_backups=10)

    # 4. Assert protected files still exist
    for name in protected_names:
        assert (backup_dir / name).exists(), f"Protected backup {name} was unexpectedly deleted!"

    # 5. Check automated files count
    remaining_automated = [
        p.name for p in backup_dir.glob("trucklead_*.db")
        if not any(bad in p.name for bad in ["before_restore", "pre_cleanup", "bak_"])
        and p.name != "trucklead_manual_export.db"
    ]
    # 12 original + 1 new = 13 total created; rotation keeps last 10
    assert len(remaining_automated) == 10, f"Expected 10 automated backups retained, got {len(remaining_automated)}: {remaining_automated}"

    # The 3 oldest automated backups should have been rotated
    assert not (backup_dir / "trucklead_20261001_120000.db").exists()
    assert not (backup_dir / "trucklead_20261002_120000.db").exists()
    assert not (backup_dir / "trucklead_20261003_120000.db").exists()

    # The newest backups must exist
    assert (backup_dir / "trucklead_20261012_120000.db").exists()
    assert new_backup.exists()


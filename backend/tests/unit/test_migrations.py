import os
import sys
import tempfile
import sqlite3
import subprocess
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def test_fresh_db_build_from_migrations():
    """
    I2: Verifies that a fresh database builds successfully from Alembic migrations
    from scratch (base -> head) and confirms that the partial unique index
    uq_companies_carrier_usdot is created and properly enforces carrier USDOT uniqueness.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name.replace("\\", "/")

    try:
        # 1. Run alembic upgrade head against the new temporary database
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0, f"Alembic upgrade head failed on fresh DB:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

        # 2. Verify that uq_companies_carrier_usdot exists in the new DB
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        idx_row = c.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND name='uq_companies_carrier_usdot'"
        ).fetchone()

        assert idx_row is not None, "Expected unique index 'uq_companies_carrier_usdot' to exist on fresh DB"
        idx_sql = idx_row[1] or ""
        assert "UNIQUE" in idx_sql.upper()
        assert "companies" in idx_sql
        assert "usdot" in idx_sql

        # 3. Test uniqueness enforcement: Two CARRIERs with the same USDOT must raise IntegrityError
        c.execute("""
            INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
            VALUES ('c-1', 'Carrier One LLC', 'CARRIER', '9988771', 'RAW')
        """)
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            c.execute("""
                INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
                VALUES ('c-2', 'Carrier Two LLC', 'CARRIER', '9988771', 'RAW')
            """)
            conn.commit()

        # 4. Partial index behavior: Two SHIPPERs or NULL USDOTs must NOT collide
        c.execute("""
            INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
            VALUES ('s-1', 'Shipper Alpha Inc', 'SHIPPER', '9988771', 'RAW')
        """)
        c.execute("""
            INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
            VALUES ('s-2', 'Shipper Beta Inc', 'SHIPPER', '9988771', 'RAW')
        """)
        c.execute("""
            INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
            VALUES ('c-3', 'Carrier Null One', 'CARRIER', NULL, 'RAW')
        """)
        c.execute("""
            INSERT INTO companies (id, company_name, lead_type, usdot, lead_status)
            VALUES ('c-4', 'Carrier Null Two', 'CARRIER', NULL, 'RAW')
        """)
        conn.commit()

        conn.close()

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

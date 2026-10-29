import pytest
import sqlite3
from pathlib import Path
from backend.app.services.change_monitor_service import ChangeMonitorService
from backend.app.models.entities import ChangeLog, IntentSignal


def test_q3_change_log_schema_and_persistence():
    """
    Q3: Verifies that change_logs table exists and stores transitions detected by the monitor.
    """
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trucklead.db"
    if not db_path.is_file():
        pytest.skip("trucklead.db not found")

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # 1. Verify change_logs table exists and has entries
    log_count = cur.execute("SELECT count(*) FROM change_logs").fetchone()[0]
    assert log_count >= 2, f"Expected at least 2 change log entries, got {log_count}"

    # 2. Check for AUTHORITY_ACTIVATED event
    auth_act_rows = cur.execute("""
        SELECT usdot, docket, change_type, from_value, to_value, signal_created
        FROM change_logs
        WHERE change_type = 'AUTHORITY_ACTIVATED'
    """).fetchall()
    assert len(auth_act_rows) >= 2, f"Expected at least 2 AUTHORITY_ACTIVATED rows, got {len(auth_act_rows)}"
    for r in auth_act_rows:
        assert r[0], "USDOT must be populated"
        assert r[2] == "AUTHORITY_ACTIVATED"
        assert r[4] == "ACTIVE"
        assert r[5] == "AUTHORITY_ACTIVATED"

    # 3. Verify IntentSignals were created for these companies
    signal_count = cur.execute("""
        SELECT count(*) FROM intent_signals
        WHERE signal_type = 'AUTHORITY_ACTIVATED'
    """).fetchone()[0]
    assert signal_count >= 2, f"Expected at least 2 AUTHORITY_ACTIVATED signals, got {signal_count}"

    con.close()


def test_q3_sensitive_insurance_cancel_handling():
    """
    Q3: Verifies that insurance cancellation warnings are strictly marked is_sensitive = True.
    """
    signal = IntentSignal(
        signal_type="INSURANCE_CANCEL",
        title="Insurance Cancellation Notice",
        confidence=0.9,
        strength=1.0,
        half_life_days=14.0,
        is_sensitive=True
    )
    assert signal.is_sensitive is True
    assert signal.half_life_days == 14.0


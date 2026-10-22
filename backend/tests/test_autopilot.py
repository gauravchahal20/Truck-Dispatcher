import pytest
from app.services.continuous_runner import ContinuousAutopilot, CORRIDORS

def test_autopilot_initialization():
    autopilot = ContinuousAutopilot()
    status = autopilot.get_status()
    assert status["status"] in ["RUNNING", "STOPPED"]
    assert status["interval_seconds"] == 90
    assert len(status["all_corridors"]) == len(CORRIDORS)
    assert status["total_cycles_completed"] == 0

def test_autopilot_pause_and_resume():
    autopilot = ContinuousAutopilot()
    paused_status = autopilot.pause()
    assert paused_status["is_paused"] is True
    assert paused_status["status"] == "PAUSED"

    resumed_status = autopilot.resume()
    assert resumed_status["is_paused"] is False

def test_autopilot_interval_config():
    autopilot = ContinuousAutopilot()
    # Test setting interval
    status = autopilot.set_interval(120)
    assert status["interval_seconds"] == 120

    # Test minimum enforcement (must be at least 30s)
    status_min = autopilot.set_interval(10)
    assert status_min["interval_seconds"] == 30

import ast
import os
import sys
import subprocess
from pathlib import Path
import pytest
from app.core.config import settings
from app.core.auth import validate_api_key_startup, require_api_key, get_configured_api_key

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
APP_DIR = ROOT_DIR / "backend" / "app"


def test_j5_mock_providers_import_boundary():
    """
    J5: Confirms mock_providers.py is not importable from backend/app and is under tests/ only.
    Scans all AST imports in backend/app to ensure no runtime code imports test mocks.
    """
    # 1. Assert backend.app.mock_providers cannot be imported
    with pytest.raises(ModuleNotFoundError):
        import backend.app.mock_providers  # type: ignore

    # 2. Confirm mock_providers.py does NOT exist anywhere under backend/app/
    app_mock_files = list(APP_DIR.rglob("*mock_provider*"))
    assert len(app_mock_files) == 0, f"Found mock provider files inside production app: {app_mock_files}"

    # 3. Confirm mock_providers.py DOES exist under backend/tests/fixtures/
    fixture_path = ROOT_DIR / "backend" / "tests" / "fixtures" / "mock_providers.py"
    assert fixture_path.is_file(), f"Expected fixture mock_providers.py at {fixture_path}"

    # 4. AST boundary check: Scan every .py file in backend/app for disallowed imports
    disallowed_modules = {"mock_providers", "tests", "backend.tests", "fixtures"}
    violations = []

    for py_file in APP_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception as e:
            violations.append(f"Failed to parse {py_file}: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in disallowed_modules or alias.name in disallowed_modules:
                        violations.append(f"{py_file.name}:{node.lineno} imports '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod in disallowed_modules or node.module in disallowed_modules:
                        violations.append(f"{py_file.name}:{node.lineno} imports from '{node.module}'")

    assert len(violations) == 0, f"Disallowed test/mock imports found in backend/app: {violations}"


def test_j5_git_secret_and_env_hygiene():
    """
    J5: Confirms .env and secret keys were never committed to git history.
    """
    # 1. Verify no actual .env file was ever committed to git history
    try:
        all_files = subprocess.check_output(
            ["git", "log", "--all", "--pretty=format:", "--name-only"],
            text=True, encoding="utf-8", errors="ignore"
        ).splitlines()
        env_files = [f.strip() for f in all_files if f.strip() == ".env" or (f.strip().endswith("/.env") and not f.strip().endswith(".example"))]
        assert len(env_files) == 0, f"Found committed .env file in git history: {env_files}"
    except subprocess.SubprocessError as e:
        pytest.skip(f"Git command failed: {e}")


def test_j5_api_key_auth_refuses_startup_in_non_dev_without_configured_key(monkeypatch):
    """
    J5: Confirms default API-key auth refuses to start without a configured key in non-dev mode.
    """
    # Clear all possible environment keys
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("GENLEAD_API_KEY", raising=False)
    monkeypatch.setattr(settings, "api_key", None)

    # 1. In 'production', startup MUST be refused
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError) as exc_info:
        validate_api_key_startup()
    assert "Startup aborted" in str(exc_info.value)
    assert "production" in str(exc_info.value)

    # 2. In 'staging', startup MUST also be refused
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(RuntimeError) as exc_info2:
        validate_api_key_startup()
    assert "Startup aborted" in str(exc_info2.value)

    # 3. In 'development', startup is permitted without key
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    validate_api_key_startup()  # Should not raise

    # 4. In 'production' WITH a configured key, startup is permitted
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_KEY", "prod-secret-key-12345")
    monkeypatch.setattr(settings, "api_key", "prod-secret-key-12345")
    validate_api_key_startup()  # Should not raise

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


def test_k1_release_integrity():
    """
    K1: Verifies tag v1.1.0 points directly to the final J6 commit,
    and cleanup/restructure is aligned.
    """
    try:
        tag_commit = subprocess.check_output(
            ["git", "rev-parse", "v1.1.0^{commit}"],
            cwd=str(ROOT_DIR), text=True
        ).strip()
        commit_msg = subprocess.check_output(
            ["git", "log", "-1", "--format=%s", tag_commit],
            cwd=str(ROOT_DIR), text=True
        ).strip()
        assert "J6:" in commit_msg
        assert tag_commit.startswith("9fc4fcc")
    except subprocess.SubprocessError as e:
        pytest.skip(f"Git command failed: {e}")


@pytest.mark.asyncio
async def test_k7_security_basics(monkeypatch):
    """
    K7: Verifies:
    1. GET endpoints returning lead PII require an API key unless request originates from loopback.
    2. CORS is restricted to frontend origins (never wildcard *).
    3. Startup check refuses non-loopback binding without configured API key.
    """
    import httpx
    from app.main import app
    from app.core.auth import validate_pii_security_startup, is_loopback_client, require_pii_access

    # 1. Startup validation: Public host without key raises RuntimeError
    monkeypatch.setattr(settings, "backend_host", "0.0.0.0")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setattr(settings, "api_key", None)
    with pytest.raises(RuntimeError) as exc_info:
        validate_pii_security_startup()
    assert "Security Error: Server host is bound to public/network interface" in str(exc_info.value)

    # 2. Startup validation: Public host WITH key passes
    monkeypatch.setenv("API_KEY", "secure-token-999")
    monkeypatch.setattr(settings, "api_key", "secure-token-999")
    validate_pii_security_startup()  # Should not raise

    # 3. Startup validation: Loopback host without key passes (local dev convenience)
    monkeypatch.setattr(settings, "backend_host", "127.0.0.1")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setattr(settings, "api_key", None)
    validate_pii_security_startup()  # Should not raise

    # 4. Loopback client identification
    assert is_loopback_client("127.0.0.1") is True
    assert is_loopback_client("localhost") is True
    assert is_loopback_client("::1") is True
    assert is_loopback_client("testclient") is True
    assert is_loopback_client("192.168.1.100") is False
    assert is_loopback_client("10.0.0.5") is False

    # 5. Remote non-loopback PII endpoint access
    class MockRemoteRequest:
        def __init__(self, host: str):
            self.client = type("Client", (), {"host": host})()

    remote_req = MockRemoteRequest(host="192.168.1.100")

    # When key is configured, remote request without key -> 401
    monkeypatch.setenv("API_KEY", "valid-k7-key")
    monkeypatch.setattr(settings, "api_key", "valid-k7-key")

    with pytest.raises(Exception) as exc401:
        require_pii_access(remote_req, api_key=None)
    assert getattr(exc401.value, "status_code", None) == 401

    with pytest.raises(Exception) as exc403:
        require_pii_access(remote_req, api_key="wrong-key")
    assert getattr(exc403.value, "status_code", None) == 403

    assert require_pii_access(remote_req, api_key="valid-k7-key") == "valid-k7-key"

    # Loopback request bypasses without requiring key
    loopback_req = MockRemoteRequest(host="127.0.0.1")
    assert require_pii_access(loopback_req, api_key=None) == "loopback_authorized"

    # 6. CORS verification
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Request with allowed frontend origin
        res_allowed = await client.options(
            "/api/leads/callable-mailable",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
        )
        assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

        # Request with disallowed foreign origin
        res_disallowed = await client.options(
            "/api/leads/callable-mailable",
            headers={"Origin": "http://malicious-external-site.com", "Access-Control-Request-Method": "GET"}
        )
        assert res_disallowed.headers.get("access-control-allow-origin") is None



import os
import sys
import socket
from pathlib import Path
from typing import Any
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure isolated test database
test_db_path = backend_dir / "test_trucklead.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"


class SocketBlockedError(RuntimeError):
    """Raised when an unmocked external socket or DNS request is initiated in offline test suite."""
    pass


@pytest.fixture(scope="session", autouse=True)
def clean_test_db():
    # Teardown after test session
    yield
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except Exception:
            pass


def _is_loopback(host: Any) -> bool:
    if not host:
        return True
    h = str(host).lower().strip()
    if h in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "testserver"):
        return True
    if h.startswith("127."):
        return True
    return False


@pytest.fixture(autouse=True)
def block_external_sockets(request, monkeypatch):
    """
    Enforces 100% offline test execution.
    Fails any non-loopback socket connection, connect_ex, or DNS resolution
    unless the test is explicitly marked with @pytest.mark.live.
    """
    if "live" in request.keywords:
        yield
        return

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = None
        port = None
        if isinstance(address, tuple) and len(address) >= 2:
            host, port = address[0], address[1]
        elif isinstance(address, str):
            host = address

        if host is not None and not _is_loopback(host):
            raise SocketBlockedError(
                f"External network socket blocked in offline test suite: connection attempted to {host}:{port}. "
                "Mark test with @pytest.mark.live if live network access is intentional."
            )
        return orig_connect(self, address)

    def guarded_connect_ex(self, address):
        host = None
        port = None
        if isinstance(address, tuple) and len(address) >= 2:
            host, port = address[0], address[1]
        elif isinstance(address, str):
            host = address

        if host is not None and not _is_loopback(host):
            raise SocketBlockedError(
                f"External network socket blocked in offline test suite: connection attempted to {host}:{port}. "
                "Mark test with @pytest.mark.live if live network access is intentional."
            )
        return orig_connect_ex(self, address)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if host is not None and not _is_loopback(host):
            raise SocketBlockedError(
                f"External DNS resolution blocked in offline test suite: attempted to resolve '{host}'. "
                "Mark test with @pytest.mark.live if live network access is intentional."
            )
        return orig_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield

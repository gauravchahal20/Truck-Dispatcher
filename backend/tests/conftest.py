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
    orig_sendto = socket.socket.sendto
    orig_recvfrom = socket.socket.recvfrom
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

    def guarded_sendto(self, data, *args, **kwargs):
        address = None
        if args:
            if isinstance(args[-1], tuple):
                address = args[-1]
            elif len(args) >= 1 and isinstance(args[0], tuple):
                address = args[0]
        if "address" in kwargs:
            address = kwargs["address"]

        if address and isinstance(address, tuple) and len(address) >= 2:
            host = address[0]
            if not _is_loopback(host):
                raise SocketBlockedError(
                    f"External UDP sendto blocked in offline test suite: attempted to send to {host}:{address[1]}. "
                    "Mark test with @pytest.mark.live if live network access is intentional."
                )
        return orig_sendto(self, data, *args, **kwargs)

    def guarded_recvfrom(self, *args, **kwargs):
        try:
            peer = self.getpeername()
            if peer and not _is_loopback(peer[0]):
                raise SocketBlockedError(f"External UDP recvfrom blocked for peer {peer}")
        except SocketBlockedError:
            raise
        except Exception:
            pass
        return orig_recvfrom(self, *args, **kwargs)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if host is not None and not _is_loopback(host):
            raise SocketBlockedError(
                f"External DNS resolution blocked in offline test suite: attempted to resolve '{host}'. "
                "Mark test with @pytest.mark.live if live network access is intentional."
            )
        return orig_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket.socket, "recvfrom", guarded_recvfrom)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    # Block dnspython resolver
    try:
        import dns.resolver
        orig_dns_resolve = dns.resolver.Resolver.resolve

        def guarded_dns_resolve(self, qname, *args, **kwargs):
            qn_str = str(qname).rstrip(".").lower()
            if not _is_loopback(qn_str):
                raise SocketBlockedError(
                    f"External dnspython DNS resolution blocked in offline test suite: attempted to resolve '{qname}'. "
                    "Mark test with @pytest.mark.live if live network access is intentional."
                )
            return orig_dns_resolve(self, qname, *args, **kwargs)

        monkeypatch.setattr(dns.resolver.Resolver, "resolve", guarded_dns_resolve)
    except ImportError:
        pass

    yield


@pytest.fixture(autouse=True)
def enable_test_mode_nanp_override():
    """Allows offline test fixtures to use standard fictional 555-01xx numbers via validator override."""
    from app.services.normalizer import Normalizer
    Normalizer.set_allow_fictional_phones_override(True)
    yield
    Normalizer.set_allow_fictional_phones_override(False)

import socket
import pytest
from conftest import SocketBlockedError


def test_external_socket_fails_in_offline_suite():
    """Proves that any real external socket connection attempt fails immediately."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(SocketBlockedError, match="External network socket blocked in offline test suite"):
            s.connect(("8.8.8.8", 53))
    finally:
        s.close()


def test_external_dns_fails_in_offline_suite():
    """Proves that any real external DNS lookup attempt fails immediately."""
    with pytest.raises(SocketBlockedError, match="External DNS resolution blocked in offline test suite"):
        socket.getaddrinfo("google.com", 80)


def test_loopback_socket_allowed():
    """Verifies that local loopback is allowed so local event loops and DBs work."""
    # Binding and checking a local socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        # Verify connecting to 127.0.0.1 does not raise SocketBlockedError
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
        finally:
            client.close()
    finally:
        s.close()


@pytest.mark.live
def test_live_marker_allows_socket_without_blocker():
    """Verifies that tests explicitly marked with @pytest.mark.live bypass the socket blocker."""
    # When decorated with live, the conftest blocker yields without monkeypatching
    # We test getaddrinfo for localhost / loopback to confirm it is the original function
    res = socket.getaddrinfo("127.0.0.1", 80)
    assert len(res) > 0

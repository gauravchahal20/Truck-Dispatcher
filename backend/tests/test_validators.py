import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.normalizer import Normalizer


def test_ssrf_blocks_private_ips():
    """Confirms RFC 1918 private IPv4 ranges are blocked."""
    private_urls = [
        "http://10.0.0.1/admin",
        "http://10.254.254.1:8080/",
        "http://172.16.0.1/",
        "http://172.31.255.254/internal",
        "http://192.168.1.1/router",
        "http://192.168.0.100:3000/api",
    ]
    for url in private_urls:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is False, f"Expected {url} to be blocked as private IP"
        assert "private" in reason.lower()


def test_ssrf_blocks_ipv6_loopback_and_local():
    """Confirms IPv6 loopback, link-local, and unique-local ranges are blocked."""
    ipv6_blocked = [
        "http://[::1]/admin",
        "http://[::]/",
        "http://[fe80::1]/link-local",
        "http://[fc00::1]/unique-local",
        "http://[fd12:3456:789a:1::1]/",
    ]
    for url in ipv6_blocked:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is False, f"Expected {url} to be blocked as dangerous IPv6"
        assert "ipv6" in reason.lower() or "blocked" in reason.lower()


def test_ssrf_blocks_ipv4_mapped_ipv6():
    """Confirms IPv4-mapped IPv6 addresses resolving to private/loopback IPv4 are blocked."""
    mapped_urls = [
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:10.0.0.1]/",
        "http://[::ffff:192.168.1.1]/",
        "http://[::ffff:169.254.169.254]/",
    ]
    for url in mapped_urls:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is False, f"Expected mapped {url} to be blocked"


def test_ssrf_blocks_loopback_and_internal_hostnames():
    """Confirms loopback and internal hostname targets are blocked."""
    loopback_urls = [
        "http://127.0.0.1:8000/docs",
        "http://127.0.0.2/",
        "http://localhost:5173/",
        "http://localhost:8000/api",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://server.local/",
    ]
    for url in loopback_urls:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is False, f"Expected {url} to be blocked"


def test_ssrf_blocks_cloud_metadata_ip():
    """Confirms cloud metadata IP 169.254.169.254 is blocked."""
    url = "http://169.254.169.254/latest/meta-data/"
    safe, reason = Normalizer.is_ssrf_safe_url(url)
    assert safe is False
    assert "metadata" in reason.lower() or "link-local" in reason.lower()


def test_ssrf_blocks_non_http_schemes():
    """Confirms non-HTTP schemes like file:// and ftp:// are blocked."""
    dangerous = [
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "ftp://internal.server/payload",
        "gopher://internal.server:70/",
    ]
    for url in dangerous:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is False
        assert "scheme" in reason.lower()


def test_ssrf_allows_public_urls():
    """Confirms legitimate public web targets are allowed."""
    public_urls = [
        "https://lonestareagle.com",
        "http://blueridgefreight.net/about-us",
        "https://www.apextransport.org/contact?ref=directory",
    ]
    for url in public_urls:
        safe, reason = Normalizer.is_ssrf_safe_url(url)
        assert safe is True, f"Expected {url} to be allowed, got error: {reason}"
        assert reason is None


def test_role_account_tiered_classification():
    """Tests tiered email categorization: generic vs departmental vs named decision maker."""
    generic_emails = [
        "info@truckcarrier.com",
        "support@apextransport.com",
        "admin@carrierops.com",
        "billing@freightdirect.com",
        "help@logistics.com",
        "contact@haul.com",
        "careers@freightlines.com",
        "office@midwesthaul.com",
    ]
    for email in generic_emails:
        assert Normalizer.classify_email_tier(email) == "generic", f"Expected {email} to be generic"
        assert Normalizer.is_role_account_email(email) is True

    departmental_emails = [
        "sales@freightlogistics.com",
        "dispatch@lonestareagle.com",
        "operations@trucking.com",
        "ops@midwesthaul.com",
        "logistics@haulers.com",
        "freight@fastfreight.com",
        "brokerage@directfreight.com",
    ]
    for email in departmental_emails:
        assert Normalizer.classify_email_tier(email) == "departmental", f"Expected {email} to be departmental"
        assert Normalizer.is_role_account_email(email) is True

    named_emails = [
        "marcus.vance@lonestareagle.com",
        "mvance@lonestareagle.com",
        "sarah.jenkins@apextransport.com",
        "jdoe@freightdirect.com",
        "david.smith@carrier.com",
    ]
    for email in named_emails:
        assert Normalizer.classify_email_tier(email) == "named", f"Expected {email} to be named individual"
        assert Normalizer.is_role_account_email(email) is False


def test_email_normalization_edge_cases():
    """Tests email syntax validation and sanitization."""
    assert Normalizer.normalize_email("  USER@CarrierDomain.com  ") == "user@carrierdomain.com"
    assert Normalizer.normalize_email("invalid-email-format") is None
    assert Normalizer.normalize_email("missing-domain@") is None
    assert Normalizer.normalize_email("@missing-user.com") is None
    assert Normalizer.normalize_email("") is None
    assert Normalizer.normalize_email(None) is None


def test_nanp_phone_validation():
    """Tests North American Numbering Plan validation rules."""
    # Valid NANP numbers (area code 2-9, exchange 2-9)
    assert Normalizer.is_valid_phone_nanp("(214) 765-4321") is True
    assert Normalizer.is_valid_phone_nanp("+14048901234") is True
    assert Normalizer.is_valid_phone_nanp("614-234-5678") is True

    # Invalid: Repeated dummy numbers
    assert Normalizer.is_valid_phone_nanp("0000000000") is False
    assert Normalizer.is_valid_phone_nanp("1111111111") is False

    # Invalid: Area code starting with 0 or 1
    assert Normalizer.is_valid_phone_nanp("012-345-6789") is False
    assert Normalizer.is_valid_phone_nanp("123-456-7890") is False

    # Invalid: Central office code starting with 0 or 1
    assert Normalizer.is_valid_phone_nanp("214-012-3456") is False
    assert Normalizer.is_valid_phone_nanp("214-123-4567") is False

    # When override is disabled, fictional TV/movie range (exchange 555, line 0100-0199) is strictly rejected
    Normalizer.set_allow_fictional_phones_override(False)
    try:
        assert Normalizer.is_valid_phone_nanp("(214) 555-0182") is False
        assert Normalizer.is_valid_phone_nanp("404-555-0105") is False
        assert Normalizer.is_valid_phone_nanp("+12145550199") is False

        # When test-mode override is injected, fictional fixture numbers pass
        assert Normalizer.is_valid_phone_nanp("(214) 555-0182", allow_fictional=True) is True
    finally:
        Normalizer.set_allow_fictional_phones_override(True)

    # Valid non-fictional 555 numbers outside 0100-0199
    assert Normalizer.is_valid_phone_nanp("(214) 555-2345") is True

    # Invalid lengths
    assert Normalizer.is_valid_phone_nanp("12345") is False
    assert Normalizer.is_valid_phone_nanp("") is False
    assert Normalizer.is_valid_phone_nanp(None) is False


@pytest.mark.asyncio
async def test_fetch_ssrf_safe_blocks_redirect_to_private_ip():
    """Verifies that redirecting to a private IP is intercepted and blocked."""
    import socket
    mock_redirect = MagicMock()
    mock_redirect.is_redirect = True
    mock_redirect.headers = {"location": "http://192.168.1.1/secret"}

    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_redirect
            mock_stream.return_value = mock_ctx

            with pytest.raises(ValueError, match="SSRF violation.*Blocked private IP"):
                await Normalizer.fetch_ssrf_safe_http("https://public-site.com/redirect", max_redirects=3)


@pytest.mark.asyncio
async def test_fetch_ssrf_safe_caps_redirect_count():
    """Verifies that exceeding the redirect limit raises ValueError."""
    import socket
    mock_redirect = MagicMock()
    mock_redirect.is_redirect = True
    mock_redirect.headers = {"location": "https://public-site.com/hop"}

    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]):
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_redirect
            mock_stream.return_value = mock_ctx

            with pytest.raises(ValueError, match="Redirect limit"):
                await Normalizer.fetch_ssrf_safe_http("https://public-site.com/start", max_redirects=2)

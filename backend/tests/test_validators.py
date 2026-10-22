import pytest
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


def test_role_account_email_detection():
    """Tests distinguishing named decision maker emails from generic company inboxes."""
    role_emails = [
        "info@truckcarrier.com",
        "sales@freightlogistics.com",
        "dispatch@lonestareagle.com",
        "support@apextransport.com",
        "admin@carrierops.com",
        "careers@freightlines.com",
        "office@midwesthaul.com",
        "billing@freightdirect.com",
    ]
    for email in role_emails:
        assert Normalizer.is_role_account_email(email) is True, f"Expected {email} to be detected as role account"

    named_emails = [
        "marcus.vance@lonestareagle.com",
        "mvance@lonestareagle.com",
        "sarah.jenkins@apextransport.com",
        "jdoe@freightdirect.com",
    ]
    for email in named_emails:
        assert Normalizer.is_role_account_email(email) is False, f"Expected {email} to be named individual"


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

    # Invalid: Fictional TV/movie range (exchange 555, line 0100-0199)
    assert Normalizer.is_valid_phone_nanp("(214) 555-0182") is False
    assert Normalizer.is_valid_phone_nanp("404-555-0105") is False

    # Invalid lengths
    assert Normalizer.is_valid_phone_nanp("12345") is False
    assert Normalizer.is_valid_phone_nanp("") is False
    assert Normalizer.is_valid_phone_nanp(None) is False

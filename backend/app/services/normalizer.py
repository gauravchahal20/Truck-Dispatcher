import re
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict, Any, List

US_STATE_ABBRS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC"
}

LEGAL_SUFFIXES = [
    r"\bllc\b", r"\bl\.l\.c\.\b", r"\binc\b", r"\bi\.n\.c\.\b", r"\bincorporated\b",
    r"\bcorp\b", r"\bcorporation\b", r"\bco\b", r"\bcompany\b", r"\bltd\b", r"\blimited\b",
    r"\btransportation\b", r"\btransport\b", r"\btrucking\b", r"\blogistics\b", r"\bfreight\b",
    r"\bexpress\b", r"\benterprises\b", r"\bgroup\b", r"\bservices\b", r"\blines\b",
    r"\bhauling\b"
]

class Normalizer:
    """Standardized cleaning and normalization engine for carrier data."""

    @staticmethod
    def normalize_company_name(name: Optional[str]) -> str:
        """Normalizes company names for deduplication and matching."""
        if not name:
            return ""
        # Lowercase and trim
        norm = name.strip().lower()
        # Remove periods first so abbreviations like l.l.c. become llc
        norm = re.sub(r"\.", "", norm)
        # Remove punctuation & symbols
        norm = re.sub(r"[^\w\s]", " ", norm)
        # Remove common legal & industry suffixes
        for suffix in LEGAL_SUFFIXES:
            norm = re.sub(suffix, " ", norm, flags=re.IGNORECASE)
        # Collapse whitespace
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm

    GENERIC_DOMAINS = {
        "safer.fmcsa.dot.gov", "fmcsa.dot.gov", "dot.gov", "google.com",
        "maps.google.com", "usdotlookup.com", "quicktransportsolutions.com",
        "clutch.co", "industryselect.com", "linkedin.com", "facebook.com",
        "yellowpages.com", "yelp.com", "manta.com", "bbb.org", "wikipedia.org",
        "carrierhub.com", "truckcarrierhub.com", "otrucking.com", "carriersource.io",
        "openstreetmap.org", "news.google.com", "indeed.com"
    }

    @staticmethod
    def normalize_domain(url_or_domain: Optional[str]) -> str:
        """Extracts clean base domain without protocol, www, port, or path."""
        if not url_or_domain:
            return ""
        raw = url_or_domain.strip().lower()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "http://" + raw
        try:
            parsed = urlparse(raw)
            domain = parsed.hostname or ""
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.strip()
        except Exception:
            return ""

    @classmethod
    def is_custom_domain(cls, domain: Optional[str]) -> bool:
        """Checks if a domain is a proprietary company domain and not a generic aggregator/search engine."""
        if not domain:
            return False
        clean = domain.strip().lower()
        if clean.startswith("www."):
            clean = clean[4:]
        return clean not in cls.GENERIC_DOMAINS and not any(clean.endswith("." + g) for g in cls.GENERIC_DOMAINS)


    @staticmethod
    def normalize_phone(phone: Optional[str]) -> str:
        """Normalizes phone numbers to standard 10-digit / E.164 string."""
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        # Handle US country code
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"+1{digits}"
        return digits

    @staticmethod
    def format_phone_display(phone: Optional[str]) -> str:
        """Formats E.164 phone into (XXX) XXX-XXXX display format."""
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        return phone

    @staticmethod
    def normalize_usdot(usdot: Optional[str]) -> Optional[str]:
        """Strips non-digits and leading noise from USDOT."""
        if not usdot:
            return None
        digits = re.sub(r"\D", "", str(usdot)).strip()
        return digits if digits else None

    @staticmethod
    def normalize_email(email: Optional[str]) -> Optional[str]:
        """Validates and normalizes email string."""
        if not email:
            return None
        em = email.strip().lower()
        # Basic email regex validation
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if re.match(pattern, em):
            return em
        return None

    @staticmethod
    def normalize_state(state: Optional[str]) -> Optional[str]:
        """Converts state name or code to 2-letter uppercase postal code."""
        if not state:
            return None
        s = state.strip().lower()
        if len(s) == 2 and s.upper() in US_STATE_ABBRS.values():
            return s.upper()
        if s in US_STATE_ABBRS:
            return US_STATE_ABBRS[s]
        # Match partial
        for name, code in US_STATE_ABBRS.items():
            if name.startswith(s) or s in name:
                return code
        return state.strip().upper() if len(state.strip()) == 2 else None

    GENERIC_INBOX_PREFIXES = {
        "info", "support", "contact", "admin", "billing", "help",
        "careers", "jobs", "team", "office", "general", "inquiries"
    }

    DEPARTMENTAL_PREFIXES = {
        "sales", "dispatch", "operations", "ops", "logistics", "freight",
        "brokerage", "service", "load", "booking"
    }

    ROLE_ACCOUNT_PREFIXES = GENERIC_INBOX_PREFIXES | DEPARTMENTAL_PREFIXES

    @classmethod
    def classify_email_tier(cls, email: Optional[str]) -> str:
        """
        Classifies an email address into:
        - 'named': individual decision maker (highest value)
        - 'departmental': sales, dispatch, ops (medium value)
        - 'generic': info, support, admin, billing (lowest value)
        """
        if not email or "@" not in email:
            return "generic"
        username = email.split("@")[0].strip().lower()
        base_user = re.split(r"[._+-]", username)[0]
        if base_user in cls.GENERIC_INBOX_PREFIXES:
            return "generic"
        if base_user in cls.DEPARTMENTAL_PREFIXES:
            return "departmental"
        return "named"

    @classmethod
    def is_role_account_email(cls, email: Optional[str]) -> bool:
        """Determines if an email address is a generic or departmental role account."""
        return cls.classify_email_tier(email) in ("generic", "departmental")

    @classmethod
    def is_ssrf_safe_url(cls, url: Optional[str], check_dns: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a URL is safe to fetch via crawler/HTTP client,
        blocking private, loopback, link-local, cloud metadata, IPv6 mapped/local, and internal IPs.
        """
        import ipaddress

        if not url:
            return False, "URL is empty"

        raw = url.strip()
        parsed = urlparse(raw)

        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Unsupported scheme: {parsed.scheme} (only http/https allowed)"

        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return False, "Missing hostname"

        # Check explicit loopback & internal hostnames
        if hostname in ("localhost", "local", "broadcasthost", "metadata.google.internal"):
            return False, f"Blocked internal hostname: {hostname}"

        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False, f"Blocked internal domain: {hostname}"

        # Clean bracket notation for IPv6 URLs like http://[::1]:80/
        clean_host = hostname.strip("[]")

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(clean_host)
            blocked, reason = cls._is_blocked_ip(ip)
            if blocked:
                return False, reason
        except ValueError:
            # Not an IP literal, it is a regular domain name
            if check_dns:
                try:
                    import socket
                    addr_info = socket.getaddrinfo(clean_host, None)
                    for family, _, _, _, sockaddr in addr_info:
                        resolved_ip_str = sockaddr[0]
                        resolved_ip = ipaddress.ip_address(resolved_ip_str)
                        blocked, reason = cls._is_blocked_ip(resolved_ip)
                        if blocked:
                            return False, f"Resolved IP {resolved_ip_str} blocked: {reason}"
                except Exception as e:
                    return False, f"DNS resolution failed or blocked: {str(e)}"

        return True, None

    @classmethod
    def _is_blocked_ip(cls, ip) -> Tuple[bool, Optional[str]]:
        """Checks if an IPv4 or IPv6 address is dangerous/internal."""
        import ipaddress

        # Check IPv6 IPv4-mapped addresses (e.g., ::ffff:127.0.0.1 or ::ffff:10.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped:
                return cls._is_blocked_ip(ip.ipv4_mapped)
            if ip.is_loopback:
                return True, f"Blocked IPv6 loopback IP: {ip}"
            if ip.is_link_local:
                return True, f"Blocked IPv6 link-local IP: {ip}"
            if ip.is_private:
                return True, f"Blocked IPv6 private IP: {ip}"
            if ip.is_reserved or ip.is_unspecified:
                return True, f"Blocked IPv6 reserved/unspecified IP: {ip}"
            if ip.is_multicast:
                return True, f"Blocked IPv6 multicast IP: {ip}"

        # IPv4 checks
        if str(ip) == "169.254.169.254":
            return True, "Blocked cloud metadata endpoint"
        if ip.is_loopback:
            return True, f"Blocked loopback IP: {ip}"
        if ip.is_link_local:
            return True, f"Blocked link-local IP: {ip}"
        if ip.is_private:
            return True, f"Blocked private IP: {ip}"
        if ip.is_reserved:
            return True, f"Blocked reserved IP: {ip}"
        if ip.is_multicast:
            return True, f"Blocked multicast IP: {ip}"

        return False, None

    @classmethod
    async def fetch_ssrf_safe_http(
        cls,
        url: str,
        max_redirects: int = 3,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
        max_bytes: int = 2 * 1024 * 1024,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, bytes, Dict[str, str]]:
        """
        Safely fetches an HTTP URL with:
        - Pre-flight SSRF check
        - DNS resolution verification
        - SSRF verification on every redirect hop
        - Max redirect cap
        - Connect and read timeouts
        - Response body size cap
        """
        import httpx
        from urllib.parse import urljoin

        current_url = url
        req_headers = headers or {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for hop in range(max_redirects + 1):
            safe, reason = cls.is_ssrf_safe_url(current_url, check_dns=True)
            if not safe:
                raise ValueError(f"SSRF violation on {current_url}: {reason}")

            timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=5.0, pool=5.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                async with client.stream("GET", current_url, headers=req_headers) as response:
                    if response.is_redirect:
                        if hop >= max_redirects:
                            raise ValueError(f"Redirect limit ({max_redirects}) exceeded")
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect response missing Location header")
                        current_url = urljoin(current_url, location)
                        continue

                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > max_bytes:
                            raise ValueError(f"Response size exceeded limit ({max_bytes} bytes)")

                    return response.status_code, bytes(content), dict(response.headers)

        raise ValueError(f"Redirect limit ({max_redirects}) exceeded")

    @staticmethod
    def is_valid_phone_nanp(phone: Optional[str]) -> bool:
        """
        Validates North American Numbering Plan (NANP) phone compliance.
        Format: +1NXXNXXXXXX where N=2-9, X=0-9. Rejects fictional/dummy ranges.
        """
        if not phone:
            return False
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            return False

        # Reject identical repeated digits (e.g., 0000000000, 1111111111)
        if len(set(digits)) <= 1:
            return False

        # NANP rules: area code cannot start with 0 or 1; central office code cannot start with 0 or 1
        area_code = digits[:3]
        co_code = digits[3:6]
        line_num = digits[6:10]

        if area_code[0] in ("0", "1"):
            return False
        if co_code[0] in ("0", "1"):
            return False

        # Reject US fictional range reserved for movies/TV (area code 555, exchange 0100-0199)
        # Note: 555-0100 through 555-0199 in ANY area code or 555 exchange
        if co_code == "555" and 100 <= int(line_num) <= 199:
            return False

        return True


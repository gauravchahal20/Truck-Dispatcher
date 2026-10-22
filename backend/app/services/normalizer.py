import re
from urllib.parse import urlparse
from typing import Optional, Tuple

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

    ROLE_ACCOUNT_PREFIXES = {
        "info", "support", "sales", "dispatch", "contact", "admin",
        "billing", "help", "careers", "jobs", "team", "office",
        "marketing", "operations", "service", "inquiries", "general"
    }

    @classmethod
    def is_role_account_email(cls, email: Optional[str]) -> bool:
        """Determines if an email address is a generic departmental role account rather than an individual."""
        if not email or "@" not in email:
            return False
        username = email.split("@")[0].strip().lower()
        # Clean special chars from username for comparison (e.g. info+lead -> info)
        base_user = re.split(r"[._+-]", username)[0]
        return base_user in cls.ROLE_ACCOUNT_PREFIXES

    @staticmethod
    def is_ssrf_safe_url(url: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a URL is safe to fetch via crawler/HTTP client,
        blocking private, loopback, link-local, cloud metadata, and internal IPs.
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

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            # Specific cloud metadata IP (169.254.169.254)
            if str(ip) == "169.254.169.254":
                return False, "Blocked cloud metadata endpoint"
            if ip.is_loopback:
                return False, f"Blocked loopback IP: {ip}"
            if ip.is_link_local:
                return False, f"Blocked link-local IP: {ip}"
            if ip.is_private:
                return False, f"Blocked private IP: {ip}"
            if ip.is_reserved:
                return False, f"Blocked reserved IP: {ip}"
            if ip.is_multicast:
                return False, f"Blocked multicast IP: {ip}"
        except ValueError:
            # Not an IP literal, it is a regular domain name
            pass

        return True, None

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


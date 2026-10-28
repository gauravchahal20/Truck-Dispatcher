import re
from datetime import datetime
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

US_GEO_REGIONS = {
    "SE": {"AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "VA", "WV"},
    "MW": {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"},
    "NE": {"CT", "DE", "ME", "MD", "MA", "NH", "NJ", "NY", "PA", "RI", "VT", "DC"},
    "SW": {"AZ", "NM", "OK", "TX"},
    "W":  {"AK", "CA", "CO", "HI", "ID", "MT", "NV", "OR", "UT", "WA", "WY"},
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


    STATE_TIMEZONES = {
        # Eastern
        "CT": "America/New_York", "DE": "America/New_York", "FL": "America/New_York",
        "GA": "America/New_York", "IN": "America/Indiana/Indianapolis", "KY": "America/New_York",
        "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
        "MI": "America/Detroit", "NH": "America/New_York", "NJ": "America/New_York",
        "NY": "America/New_York", "NC": "America/New_York", "OH": "America/New_York",
        "PA": "America/New_York", "RI": "America/New_York", "SC": "America/New_York",
        "VT": "America/New_York", "VA": "America/New_York", "WV": "America/New_York",
        "DC": "America/New_York",
        # Central
        "AL": "America/Chicago", "AR": "America/Chicago", "IL": "America/Chicago",
        "IA": "America/Chicago", "KS": "America/Chicago", "LA": "America/Chicago",
        "MN": "America/Chicago", "MS": "America/Chicago", "MO": "America/Chicago",
        "NE": "America/Chicago", "ND": "America/Chicago", "OK": "America/Chicago",
        "SD": "America/Chicago", "TN": "America/Chicago", "TX": "America/Chicago",
        "WI": "America/Chicago",
        # Mountain
        "AZ": "America/Phoenix", "CO": "America/Denver", "ID": "America/Boise",
        "MT": "America/Denver", "NM": "America/Denver", "UT": "America/Denver",
        "WY": "America/Denver",
        # Pacific
        "CA": "America/Los_Angeles", "NV": "America/Los_Angeles",
        "OR": "America/Los_Angeles", "WA": "America/Los_Angeles",
        # Alaska & Hawaii
        "AK": "America/Anchorage", "HI": "Pacific/Honolulu"
    }

    AREA_CODE_TIMEZONES = {
        "214": "America/Chicago", "972": "America/Chicago", "469": "America/Chicago",
        "713": "America/Chicago", "281": "America/Chicago", "832": "America/Chicago",
        "512": "America/Chicago", "210": "America/Chicago", "817": "America/Chicago",
        "404": "America/New_York", "770": "America/New_York", "678": "America/New_York",
        "216": "America/New_York", "614": "America/New_York", "513": "America/New_York",
        "305": "America/New_York", "786": "America/New_York", "954": "America/New_York",
        "704": "America/New_York", "919": "America/New_York", "615": "America/Chicago",
        "312": "America/Chicago", "773": "America/Chicago", "213": "America/Los_Angeles",
        "310": "America/Los_Angeles", "415": "America/Los_Angeles", "909": "America/Los_Angeles"
    }

    @staticmethod
    def to_e164(phone: Optional[str]) -> Optional[str]:
        """Normalizes any phone string to valid E.164 (+1XXXXXXXXXX) format."""
        if not phone:
            return None
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) > 11 and digits.startswith("1"):
            return f"+{digits[:11]}"
        return None

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> str:
        """Normalizes phone numbers to standard 10-digit / E.164 string."""
        return Normalizer.to_e164(phone) or (re.sub(r"\D", "", str(phone)) if phone else "")

    @staticmethod
    def format_phone_display(phone: Optional[str], include_country_code: bool = True) -> str:
        """Formats E.164 phone into '+1 (XXX) XXX-XXXX' or '(XXX) XXX-XXXX' display format."""
        if not phone:
            return ""
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            prefix = "+1 " if include_country_code else ""
            return f"{prefix}({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        return str(phone)

    @staticmethod
    def get_dial_link(phone: Optional[str]) -> Optional[str]:
        """Generates tel:+1... URI link for click-to-call."""
        e164 = Normalizer.to_e164(phone)
        return f"tel:{e164}" if e164 else None

    @classmethod
    def get_timezone_and_windows(
        cls,
        state: Optional[str],
        phone: Optional[str] = None,
        reference_date: Optional[datetime] = None
    ) -> Tuple[str, str, str]:
        """
        Calculates the company/carrier local timezone, local call window (09:00 - 17:00 local),
        and the operator's equivalent in Asia/Kolkata (IST) dynamically using IANA zoneinfo across DST transitions.
        Returns: (tz_name, local_window_str, ist_window_str)
        """
        import zoneinfo
        from datetime import datetime

        norm_state = cls.normalize_state(state) if state else None
        tz_name = cls.STATE_TIMEZONES.get(norm_state) if norm_state else None

        if not tz_name and phone:
            digits = re.sub(r"\D", "", str(phone))
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            if len(digits) >= 3:
                area = digits[:3]
                tz_name = cls.AREA_CODE_TIMEZONES.get(area)

        if not tz_name:
            tz_name = "America/Chicago"  # Central freight hub default if undetermined

        try:
            local_tz = zoneinfo.ZoneInfo(tz_name)
            ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            ref = reference_date or datetime.now()
            dt_start = datetime(ref.year, ref.month, ref.day, 9, 0, tzinfo=local_tz)
            dt_end = datetime(ref.year, ref.month, ref.day, 17, 0, tzinfo=local_tz)

            ist_start = dt_start.astimezone(ist_tz)
            ist_end = dt_end.astimezone(ist_tz)

            tz_abbr = dt_start.tzname() or "Local"
            local_window = f"09:00 - 17:00 {tz_abbr}"
            ist_window = f"{ist_start.strftime('%H:%M')} - {ist_end.strftime('%H:%M')} IST"
            return tz_name, local_window, ist_window
        except Exception:
            return tz_name, "09:00 - 17:00 Local", "19:30 - 03:30 IST"

    @classmethod
    def get_dual_call_windows(
        cls,
        state: Optional[str],
        phone: Optional[str],
        reference_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        L2e: Computes dual call windows (business state local vs area code local)
        and the IST equivalent for each, alongside area code state and mismatch flag.
        """
        phone_st = cls.get_state_for_phone(phone)
        bus_st = cls.normalize_state(state) if state else None
        mismatch = bool(phone_st and bus_st and phone_st != bus_st)

        # 1. Business State Windows
        bus_tz, bus_local, bus_ist = cls.get_timezone_and_windows(bus_st, reference_date=reference_date)

        # 2. Area Code Windows
        phone_tz, phone_local, phone_ist = cls.get_timezone_and_windows(phone_st, phone=phone, reference_date=reference_date)

        return {
            "business_state": bus_st,
            "business_timezone": bus_tz,
            "business_call_window_local": bus_local,
            "business_call_window_ist": bus_ist,
            "phone_state": phone_st,
            "phone_timezone": phone_tz,
            "phone_call_window_local": phone_local,
            "phone_call_window_ist": phone_ist,
            "phone_region_mismatch": mismatch
        }

    @staticmethod
    def normalize_usdot(usdot: Optional[str]) -> Optional[str]:
        """Strips non-digits and leading zeros from USDOT, returning canonical integer string."""
        if not usdot:
            return None
        s = str(usdot).strip()
        digits = re.sub(r"\D", "", s).strip()
        canonical = digits.lstrip("0")
        return canonical if canonical else None

    @staticmethod
    def normalize_docket(docket: Optional[str]) -> Optional[str]:
        """
        Strips non-digits and leading zeros from MC/FF/MX docket numbers,
        returning canonical integer string (e.g. 'MC-424836' -> '424836', 'MC066124' -> '66124').
        Returns None for invalid or corrupted values (e.g., replacement character \ufffd).
        """
        if not docket:
            return None
        s = str(docket).strip()
        if "\ufffd" in s or "?" in s:
            s = re.sub(r"[\ufffd\?]", "", s)
        digits = re.sub(r"\D", "", s).strip()
        canonical = digits.lstrip("0")
        return canonical if canonical else None

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

    @staticmethod
    def get_geographic_region(state: Optional[str]) -> str:
        """Returns geographic region code: SE, MW, NE, SW, W, or OTHER."""
        if not state:
            return "OTHER"
        st = state.strip().upper()
        for region, states in US_GEO_REGIONS.items():
            if st in states:
                return region
        return "OTHER"

    @staticmethod
    def get_fleet_capacity_segment(power_units: Optional[int]) -> str:
        """Categorizes fleet size into capacity segment: single_unit, small_fleet, mid_fleet, large_fleet, unknown."""
        if power_units is None or power_units <= 0:
            return "unknown"
        if power_units == 1:
            return "single_unit"
        elif 2 <= power_units <= 5:
            return "small_fleet"
        elif 6 <= power_units <= 10:
            return "mid_fleet"
        else:
            return "large_fleet"

    @staticmethod
    def get_carrier_operation_segment(carrier_operation: Optional[str]) -> str:
        """Categorizes carrier operation: interstate, intrastate, exempt_private, other."""
        if not carrier_operation:
            return "unknown"
        op = str(carrier_operation).strip().lower()
        if op in ("a", "interstate") or "interstate" in op:
            return "interstate"
        elif op in ("b", "c", "intrastate") or "intrastate" in op:
            return "intrastate"
        elif "exempt" in op or "private" in op:
            return "exempt_private"
        return "other"

    @classmethod
    def get_census_segment(
        cls,
        state: Optional[str],
        power_units: Optional[int],
        carrier_operation: Optional[str] = None
    ) -> Dict[str, str]:
        """Returns structured national census segmentation dictionary."""
        geo = cls.get_geographic_region(state)
        cap = cls.get_fleet_capacity_segment(power_units)
        op = cls.get_carrier_operation_segment(carrier_operation)
        segment_code = f"{geo}_{cap}"
        return {
            "geo_region": geo,
            "capacity_segment": cap,
            "operation_segment": op,
            "composite_segment": segment_code
        }

    @classmethod
    def get_state_for_phone(cls, phone: Optional[str]) -> Optional[str]:
        """Resolves the US 2-letter state postal abbreviation from a phone number using canonical NANP area-code table."""
        if not phone:
            return None
        from ..core.nanp_data import NANP_AREA_CODES
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) == 11 and digits.startswith("1"):
            area_code = digits[1:4]
        elif len(digits) == 10:
            area_code = digits[0:3]
        else:
            return None

        # 1. Primary: Direct lookup in canonical NANP area-code table
        if area_code in NANP_AREA_CODES:
            return NANP_AREA_CODES[area_code]

        # 2. Secondary fallback via phonenumbers geocoder for newly issued overlays
        try:
            import phonenumbers
            from phonenumbers import geocoder
            e164 = f"+1{digits[-10:]}"
            parsed = phonenumbers.parse(e164)
            desc = geocoder.description_for_number(parsed, "en")
            if desc:
                desc_lower = desc.lower().strip()
                if "d.c." in desc_lower or "district of columbia" in desc_lower:
                    return "DC"
                for s_name, s_code in US_STATE_ABBRS.items():
                    if s_name == "district of columbia":
                        continue
                    if s_name == desc_lower or desc.endswith(f", {s_code}") or f", {s_code}" in desc:
                        return s_code
        except Exception:
            pass
        return None

    FREE_WEBMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
        "icloud.com", "mail.com", "zoho.com", "protonmail.com", "proton.me",
        "live.com", "msn.com", "yandex.com", "gmx.com", "comcast.net",
        "sbcglobal.net", "att.net", "verizon.net", "cox.net", "charter.net",
        "bellsouth.net", "rocketmail.com", "aim.com"
    }

    GENERIC_INBOX_PREFIXES = {
        "info", "support", "contact", "admin", "administrator", "billing", "help",
        "careers", "jobs", "team", "office", "general", "inquiries", "inquiry"
    }

    DEPARTMENTAL_PREFIXES = {
        "sales", "dispatch", "operations", "ops", "logistics", "freight",
        "brokerage", "service", "load", "loads", "booking"
    }

    ROLE_ACCOUNT_PREFIXES = GENERIC_INBOX_PREFIXES | DEPARTMENTAL_PREFIXES

    @classmethod
    def classify_email_tier(cls, email: Optional[str]) -> str:
        """
        Classifies an email address by local part and domain:
        - 'generic': role/generic inbox (info, admin, support, billing, office)
        - 'departmental': departmental role account (sales, dispatch, operations)
        - 'personal_webmail': free webmail provider with a personal/named local part
        - 'named': individual named person on a custom / company domain
        """
        if not email or "@" not in email:
            return "generic"
        parts = email.strip().lower().split("@")
        username = parts[0].strip()
        domain = parts[1].strip() if len(parts) > 1 else ""

        base_user = re.split(r"[._+-]", username)[0]
        if base_user in cls.GENERIC_INBOX_PREFIXES or username in cls.GENERIC_INBOX_PREFIXES:
            return "generic"
        if base_user in cls.DEPARTMENTAL_PREFIXES or username in cls.DEPARTMENTAL_PREFIXES:
            return "departmental"

        # Check if domain is free webmail
        is_free_webmail = domain in cls.FREE_WEBMAIL_DOMAINS or any(
            domain.endswith("." + fwd) for fwd in cls.FREE_WEBMAIL_DOMAINS
        )
        if is_free_webmail:
            return "personal_webmail"

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

    _ALLOW_FICTIONAL_PHONES_OVERRIDE: bool = False

    @classmethod
    def set_allow_fictional_phones_override(cls, allow: bool):
        """Allows tests to inject a test-mode override to accept fictional 555-01xx numbers in fixtures."""
        cls._ALLOW_FICTIONAL_PHONES_OVERRIDE = allow

    @classmethod
    def is_valid_phone_nanp(cls, phone: Optional[str], allow_fictional: bool = False) -> bool:
        """
        Validates North American Numbering Plan (NANP) phone compliance.
        Format: +1NXXNXXXXXX where N=2-9, X=0-9. Rejects fictional/dummy ranges unless test-mode override is active.
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
        # unless allow_fictional is True or test override is active
        if not allow_fictional and not cls._ALLOW_FICTIONAL_PHONES_OVERRIDE:
            if co_code == "555" and 100 <= int(line_num) <= 199:
                return False

        return True


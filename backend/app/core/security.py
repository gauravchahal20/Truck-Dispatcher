import re
from urllib.parse import urlparse
from typing import List, Optional
from .config import config

class SecurityGuard:
    """Enforces domain allowlists, anti-bot/CAPTCHA detection, and safe browsing rules."""

    CAPTCHA_INDICATORS = [
        "recaptcha",
        "hcaptcha",
        "cf-turnstile",
        "challenge-platform",
        "security check",
        "please verify you are a human",
        "bot detection",
        "access denied",
        "attention required",
        "cloudflare"
    ]

    @classmethod
    def get_domain(cls, url: str) -> str:
        """Extracts normalized hostname from URL."""
        if not url:
            return ""
        try:
            parsed = urlparse(url if "://" in url else f"http://{url}")
            return (parsed.hostname or "").lower()
        except Exception:
            return ""

    @classmethod
    def is_domain_allowed(cls, url: str, extra_allowed: Optional[List[str]] = None) -> bool:
        """Checks whether the domain is permitted by configured allowlist."""
        domain = cls.get_domain(url)
        if not domain:
            return False

        # Block malicious/unsupported TLDs
        for pattern in config.security.blocked_domains:
            if pattern.startswith("*.") and domain.endswith(pattern[1:]):
                return False
            elif domain == pattern:
                return False

        # Company websites (during enrichment) are dynamically allowed if valid web domains
        allowed_list = set(config.security.allowed_domains)
        if extra_allowed:
            allowed_list.update(extra_allowed)

        for allowed in allowed_list:
            if domain == allowed or domain.endswith("." + allowed):
                return True

        # If it's an HTTP/HTTPS company website target, allow standard TLDs for research
        valid_tlds = (".com", ".net", ".org", ".co", ".us", ".io", ".biz", ".info", ".transport")
        if any(domain.endswith(tld) for tld in valid_tlds):
            return True

        return False

    @classmethod
    def detect_captcha_or_block(cls, html_content: str, status_code: int = 200) -> Optional[str]:
        """Detects if a response is a CAPTCHA, bot challenge, or Cloudflare wall."""
        if status_code in (403, 429, 503):
            return f"HTTP_{status_code}_BLOCKED"

        if not html_content:
            return None

        content_lower = html_content[:20000].lower()
        for indicator in cls.CAPTCHA_INDICATORS:
            if indicator in content_lower:
                return f"CHALLENGE_DETECTED_{indicator.upper().replace(' ', '_')}"

        return None

import re
import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
import httpx
from sqlalchemy import select

from ..core.config import config, settings
from ..models.entities import PhoneVerificationCache, SuppressionEntry
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.verifier.phone")


@dataclass
class PhoneVerificationResult:
    phone_e164: str
    valid: bool
    line_type: str  # "mobile", "landline", "voip", "tollfree", "unknown"
    carrier_name: Optional[str]
    country_code: str
    phone_verification_status: str  # "VERIFIED", "INVALID", "UNREACHABLE", "UNKNOWN"
    provider: str  # "twilio", "telnyx", "numverify", "mock", "none"
    raw_status: Optional[str]
    cost: float
    verified_at: datetime
    cached: bool = False


class BasePhoneProvider(ABC):
    """Abstract interface for phone line type intelligence & verification."""
    name: str = "base"
    cost_per_lookup: float = 0.0

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if valid API credentials exist."""
        pass

    @abstractmethod
    async def verify(self, phone_e164: str) -> PhoneVerificationResult:
        """Executes provider phone lookup."""
        pass


class TwilioLookupProvider(BasePhoneProvider):
    """Twilio Lookup v2 with line_type_intelligence."""
    name = "twilio"
    cost_per_lookup = 0.015

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID") or settings.twilio_account_sid
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN") or settings.twilio_auth_token

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    async def verify(self, phone_e164: str) -> PhoneVerificationResult:
        now = datetime.now(timezone.utc)
        if not self.is_configured():
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="UNKNOWN",
                provider=self.name,
                raw_status="NOT_CONFIGURED",
                cost=0.0,
                verified_at=now
            )

        url = f"https://lookups.twilio.com/v2/PhoneNumbers/{phone_e164}?Fields=line_type_intelligence"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, auth=(self.account_sid, self.auth_token))
            if resp.status_code == 200:
                data = resp.json()
                valid = data.get("valid", False)
                lt_data = data.get("line_type_intelligence") or {}
                raw_type = (lt_data.get("type") or "unknown").lower()
                carrier = lt_data.get("carrier_name")
                c_code = data.get("country_code") or "US"

                norm_type = "mobile" if "mobile" in raw_type else (
                    "landline" if "landline" in raw_type else (
                        "voip" if "voip" in raw_type else (
                            "tollfree" if "toll" in raw_type else "unknown"
                        )
                    )
                )
                v_status = "VERIFIED" if valid and norm_type != "unknown" else ("INVALID" if not valid else "UNKNOWN")

                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=valid,
                    line_type=norm_type,
                    carrier_name=carrier,
                    country_code=c_code,
                    phone_verification_status=v_status,
                    provider=self.name,
                    raw_status=raw_type,
                    cost=self.cost_per_lookup,
                    verified_at=now
                )
            elif resp.status_code == 404:
                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=False,
                    line_type="unknown",
                    carrier_name=None,
                    country_code="US",
                    phone_verification_status="INVALID",
                    provider=self.name,
                    raw_status="NOT_FOUND",
                    cost=self.cost_per_lookup,
                    verified_at=now
                )
            else:
                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=False,
                    line_type="unknown",
                    carrier_name=None,
                    country_code="US",
                    phone_verification_status="UNKNOWN",
                    provider=self.name,
                    raw_status=f"HTTP_{resp.status_code}",
                    cost=0.0,
                    verified_at=now
                )


class TelnyxProvider(BasePhoneProvider):
    """Telnyx Number Lookup API."""
    name = "telnyx"
    cost_per_lookup = 0.005

    def __init__(self):
        self.api_key = os.getenv("TELNYX_API_KEY") or settings.telnyx_api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def verify(self, phone_e164: str) -> PhoneVerificationResult:
        now = datetime.now(timezone.utc)
        if not self.is_configured():
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="UNKNOWN",
                provider=self.name,
                raw_status="NOT_CONFIGURED",
                cost=0.0,
                verified_at=now
            )

        url = f"https://api.telnyx.com/v2/number_lookup/{phone_e164}?type=carrier"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                valid = data.get("valid_number", False)
                carrier_data = data.get("carrier") or {}
                raw_type = (carrier_data.get("type") or "unknown").lower()
                carrier = carrier_data.get("name")
                c_code = data.get("country_code") or "US"

                norm_type = "mobile" if "mobile" in raw_type or "wireless" in raw_type else (
                    "landline" if "landline" in raw_type or "wireline" in raw_type else (
                        "voip" if "voip" in raw_type else "unknown"
                    )
                )
                v_status = "VERIFIED" if valid and norm_type != "unknown" else ("INVALID" if not valid else "UNKNOWN")

                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=valid,
                    line_type=norm_type,
                    carrier_name=carrier,
                    country_code=c_code,
                    phone_verification_status=v_status,
                    provider=self.name,
                    raw_status=raw_type,
                    cost=self.cost_per_lookup,
                    verified_at=now
                )
            else:
                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=False,
                    line_type="unknown",
                    carrier_name=None,
                    country_code="US",
                    phone_verification_status="UNKNOWN",
                    provider=self.name,
                    raw_status=f"HTTP_{resp.status_code}",
                    cost=0.0,
                    verified_at=now
                )


class NumVerifyProvider(BasePhoneProvider):
    """NumVerify API Provider."""
    name = "numverify"
    cost_per_lookup = 0.003

    def __init__(self):
        self.api_key = os.getenv("NUMVERIFY_API_KEY") or settings.numverify_api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def verify(self, phone_e164: str) -> PhoneVerificationResult:
        now = datetime.now(timezone.utc)
        if not self.is_configured():
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="UNKNOWN",
                provider=self.name,
                raw_status="NOT_CONFIGURED",
                cost=0.0,
                verified_at=now
            )

        clean_num = phone_e164.lstrip("+")
        url = f"http://apilayer.net/api/validate?access_key={self.api_key}&number={clean_num}&country_code=US"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                valid = data.get("valid", False)
                raw_type = (data.get("line_type") or "unknown").lower()
                carrier = data.get("carrier")
                c_code = data.get("country_code") or "US"

                norm_type = "mobile" if "mobile" in raw_type else (
                    "landline" if "landline" in raw_type else (
                        "voip" if "voip" in raw_type or "special" in raw_type else "unknown"
                    )
                )
                v_status = "VERIFIED" if valid and norm_type != "unknown" else ("INVALID" if not valid else "UNKNOWN")

                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=valid,
                    line_type=norm_type,
                    carrier_name=carrier,
                    country_code=c_code,
                    phone_verification_status=v_status,
                    provider=self.name,
                    raw_status=raw_type,
                    cost=self.cost_per_lookup,
                    verified_at=now
                )
            else:
                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=False,
                    line_type="unknown",
                    carrier_name=None,
                    country_code="US",
                    phone_verification_status="UNKNOWN",
                    provider=self.name,
                    raw_status=f"HTTP_{resp.status_code}",
                    cost=0.0,
                    verified_at=now
                )


class MockPhoneProvider(BasePhoneProvider):
    """Deterministic mock provider for unit tests and local simulation."""
    name = "mock"
    cost_per_lookup = 0.005

    def __init__(self, override_map: Optional[Dict[str, Dict[str, Any]]] = None):
        self.override_map = override_map or {}

    def is_configured(self) -> bool:
        return True

    async def verify(self, phone_e164: str) -> PhoneVerificationResult:
        now = datetime.now(timezone.utc)
        if phone_e164 in self.override_map:
            cfg = self.override_map[phone_e164]
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=cfg.get("valid", True),
                line_type=cfg.get("line_type", "mobile"),
                carrier_name=cfg.get("carrier_name", "Mock Wireless"),
                country_code=cfg.get("country_code", "US"),
                phone_verification_status=cfg.get("phone_verification_status", "VERIFIED"),
                provider=self.name,
                raw_status=cfg.get("raw_status", "mock_valid"),
                cost=self.cost_per_lookup,
                verified_at=now
            )

        # Deterministic simulation based on last digits
        last_digit = phone_e164[-1] if phone_e164 else "0"
        if last_digit in ("0", "9"):
            # Invalid number simulation
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="INVALID",
                provider=self.name,
                raw_status="mock_invalid",
                cost=self.cost_per_lookup,
                verified_at=now
            )
        elif last_digit in ("1", "2", "3"):
            # Mobile
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="mobile",
                carrier_name="Verizon Wireless",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="mobile",
                cost=self.cost_per_lookup,
                verified_at=now
            )
        elif last_digit in ("4", "5"):
            # Landline
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="landline",
                carrier_name="AT&T Corp",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="landline",
                cost=self.cost_per_lookup,
                verified_at=now
            )
        else:
            # VoIP
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="voip",
                carrier_name="Bandwidth.com / RingCentral",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="voip",
                cost=self.cost_per_lookup,
                verified_at=now
            )


class PhoneVerifier:
    """
    Pluggable phone verification orchestrator.
    Enforces:
    - E.164 normalization
    - 30-day SQLite caching
    - Per-lead ($0.05) and per-run ($5.00) cost caps
    - Returns UNKNOWN (never VERIFIED) without API keys
    - Sole proprietor mobile manual call & DNC flags
    """

    def __init__(self, provider_override: Optional[BasePhoneProvider] = None):
        self.providers: Dict[str, BasePhoneProvider] = {
            "twilio": TwilioLookupProvider(),
            "telnyx": TelnyxProvider(),
            "numverify": NumVerifyProvider(),
        }
        if provider_override:
            self.providers[provider_override.name] = provider_override
            self.default_provider_name = provider_override.name
        else:
            self.default_provider_name = config.contact_verification.phone.default_provider

        self.cost_cap_per_lead: float = config.contact_verification.phone.cost_cap_per_lead
        self.cost_cap_per_run: float = config.contact_verification.phone.cost_cap_per_run
        self.current_run_cost: float = 0.0

    def reset_run_cost(self):
        """Resets cumulative run cost counter."""
        self.current_run_cost = 0.0

    @classmethod
    def corroborate_phone(cls, phone_e164: Optional[str], sources: Optional[List[str]] = None) -> str:
        """
        Labels phone status based on source corroboration:
        - If seen across >= 2 independent sources (e.g. census, website, google_places): CORROBORATED
        - If valid format but only 1 source: FORMAT_OK
        - If invalid format / missing: INVALID
        """
        if not phone_e164 or not Normalizer.to_e164(phone_e164):
            return "INVALID"
        unique_sources = set(s.strip().lower() for s in (sources or []) if s and s.strip())
        if len(unique_sources) >= 2:
            return "CORROBORATED"
        return "FORMAT_OK"

    async def verify_phone(
        self,
        session,
        raw_phone: Optional[str],
        lead_cost_accumulated: float = 0.0,
        provider_name: Optional[str] = None,
        sources_seen: Optional[List[str]] = None
    ) -> PhoneVerificationResult:
        """
        Verifies phone number against cache and configured external providers.
        """
        now = datetime.now(timezone.utc)
        phone_e164 = Normalizer.to_e164(raw_phone)
        if not phone_e164:
            return PhoneVerificationResult(
                phone_e164="",
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="INVALID",
                provider="none",
                raw_status="INVALID_FORMAT",
                cost=0.0,
                verified_at=now
            )

        # 1. Check 30-Day SQLite Cache
        cached_entry = await session.get(PhoneVerificationCache, phone_e164)
        if cached_entry and cached_entry.expires_at:
            exp_at = cached_entry.expires_at
            if exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            if exp_at > now:
                return PhoneVerificationResult(
                phone_e164=cached_entry.phone_e164,
                valid=cached_entry.valid,
                line_type=cached_entry.line_type or "unknown",
                carrier_name=cached_entry.carrier_name,
                country_code=cached_entry.country_code or "US",
                phone_verification_status=cached_entry.phone_verification_status,
                provider=cached_entry.provider or "cache",
                raw_status=cached_entry.raw_status,
                cost=0.0,
                verified_at=cached_entry.cached_at or now,
                cached=True
            )

        # 2. Select Active Provider
        prov_key = provider_name or self.default_provider_name
        provider = self.providers.get(prov_key)

        # Check if provider is configured with credentials
        if not provider or not provider.is_configured():
            # Check other configured providers
            fallback_provider = next((p for p in self.providers.values() if p.is_configured()), None)
            if fallback_provider:
                provider = fallback_provider
            else:
                # No provider key configured: Check corroboration (FORMAT_OK or CORROBORATED)
                status = self.corroborate_phone(phone_e164, sources_seen)
                return PhoneVerificationResult(
                    phone_e164=phone_e164,
                    valid=True,
                    line_type="unknown",
                    carrier_name=None,
                    country_code="US",
                    phone_verification_status=status,
                    provider="none",
                    raw_status=f"SOURCE_CORROBORATED ({len(set(sources_seen or []))} sources)" if status == "CORROBORATED" else "FORMAT_OK_NO_PROVIDER",
                    cost=0.0,
                    verified_at=now
                )

        # 3. Check Cost Caps
        est_cost = provider.cost_per_lookup
        if (lead_cost_accumulated + est_cost) > self.cost_cap_per_lead or (self.current_run_cost + est_cost) > self.cost_cap_per_run:
            logger.warning(f"Phone verification cost cap reached (run: ${self.current_run_cost:.4f}, lead: ${lead_cost_accumulated:.4f}). Skipping external lookup.")
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="UNKNOWN",
                provider=provider.name,
                raw_status="COST_CAP_REACHED",
                cost=0.0,
                verified_at=now
            )

        # 4. Invoke Provider
        try:
            result = await provider.verify(phone_e164)
            self.current_run_cost += result.cost
        except Exception as e:
            logger.error(f"Phone verification lookup error on {phone_e164} via {provider.name}: {e}")
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=False,
                line_type="unknown",
                carrier_name=None,
                country_code="US",
                phone_verification_status="UNKNOWN",
                provider=provider.name,
                raw_status=f"ERROR: {str(e)[:50]}",
                cost=0.0,
                verified_at=now
            )

        # 5. Persist to 30-day Cache
        expires = now + timedelta(days=config.contact_verification.phone.cache_ttl_days)
        cache_item = PhoneVerificationCache(
            phone_e164=result.phone_e164,
            valid=result.valid,
            line_type=result.line_type,
            carrier_name=result.carrier_name,
            country_code=result.country_code,
            phone_verification_status=result.phone_verification_status,
            provider=result.provider,
            raw_status=result.raw_status,
            cost=result.cost,
            cached_at=now,
            expires_at=expires
        )
        await session.merge(cache_item)
        await session.commit()

        return result

    @classmethod
    def determine_call_guidance(
        cls,
        fleet_size: Optional[int],
        carrier_operation: Optional[str],
        line_type: Optional[str]
    ) -> str:
        """
        Flags mobile numbers on carriers that look like sole proprietors as
        'call manually only, check DNC'.
        """
        is_sole_prop = (
            (fleet_size == 1) or
            ("owner" in (carrier_operation or "").lower()) or
            (fleet_size is None and "sole" in (carrier_operation or "").lower())
        )
        if is_sole_prop and (line_type or "").lower() == "mobile":
            return "call manually only, check DNC"
        return "call allowed"

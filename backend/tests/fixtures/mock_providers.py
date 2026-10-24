"""
backend/tests/fixtures/mock_providers.py
Test-only mock providers and fixture data for phone verification and shipper places enrichment.
Isolated completely from production runtime services.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.services.phone_verifier import BasePhoneProvider, PhoneVerificationResult


# Recorded benchmark shipper fixtures for offline test execution
RECORDED_SHIPPER_FIXTURES: Dict[str, Dict[str, Any]] = {
    "Tesla": {
        "formatted_phone_number": "(512) 516-8177",
        "website": "https://www.tesla.com",
        "formatted_address": "13101 Tesla Rd, Austin, TX 78725",
        "contacts": [
            {"full_name": "Marcus Vance", "title": "Inbound Transportation Manager", "email": "mvance@tesla.com", "is_decision_maker": True}
        ]
    },
    "Lockheed Martin Aeronautics Co.": {
        "formatted_phone_number": "(817) 777-2000",
        "website": "https://www.lockheedmartin.com",
        "formatted_address": "1 Lockheed Blvd, Fort Worth, TX 76108",
        "contacts": [
            {"full_name": "David Sterling", "title": "Director of Logistics & Supply Chain", "email": "david.sterling@lockheedmartin.com", "is_decision_maker": True}
        ]
    },
    "Gulfstream Aerospace Corp.": {
        "formatted_phone_number": "(912) 965-3000",
        "website": "https://www.gulfstream.com",
        "formatted_address": "500 Gulfstream Rd, Savannah, GA 31408",
        "contacts": [
            {"full_name": "Elena Rostova", "title": "Freight & Traffic Superintendent", "email": "elena.rostova@gulfstream.com", "is_decision_maker": True}
        ]
    },
    "General Electric Co.": {
        "formatted_phone_number": "(513) 243-2000",
        "website": "https://www.ge.com",
        "formatted_address": "1 Neumann Way, Cincinnati, OH 45215",
        "contacts": [
            {"full_name": "Thomas Wright", "title": "Global Logistics Operations Leader", "email": "thomas.wright@ge.com", "is_decision_maker": True}
        ]
    }
}


class MockPlacesProvider:
    """Mock Google Places provider returning recorded shipper contacts for offline benchmarks."""
    name = "mock_google_places"

    def is_configured(self) -> bool:
        return True

    async def search_place(self, company_name: str, city: Optional[str] = None, state: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for key, data in RECORDED_SHIPPER_FIXTURES.items():
            if key.lower() in company_name.lower() or company_name.lower() in key.lower():
                return data
        return None


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
        elif last_digit in ("1", "2"):
            # Landline simulation
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="landline",
                carrier_name="Mock Telecom",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="mock_landline",
                cost=self.cost_per_lookup,
                verified_at=now
            )
        elif last_digit == "8":
            # VoIP simulation
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="voip",
                carrier_name="Mock VoIP",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="mock_voip",
                cost=self.cost_per_lookup,
                verified_at=now
            )
        else:
            # Valid mobile carrier
            return PhoneVerificationResult(
                phone_e164=phone_e164,
                valid=True,
                line_type="mobile",
                carrier_name="Mock Wireless",
                country_code="US",
                phone_verification_status="VERIFIED",
                provider=self.name,
                raw_status="mock_valid",
                cost=self.cost_per_lookup,
                verified_at=now
            )

import re
from typing import List, Optional, Tuple
from ..models.entities import Contact
from ..core.config import config

DM_TITLE_RANKINGS = {
    "owner": 100,
    "co-owner": 98,
    "founder": 95,
    "co-founder": 94,
    "president": 90,
    "ceo": 88,
    "chief executive officer": 88,
    "managing partner": 85,
    "principal": 84,
    "vice president": 80,
    "vp of operations": 79,
    "director of operations": 78,
    "fleet manager": 75,
    "fleet director": 74,
    "operations manager": 72,
    "general manager": 70,
    "terminal manager": 68,
    "dispatch manager": 65,
    "lead dispatcher": 62,
    "safety director": 60,
    "transportation coordinator": 55,
    "logistics coordinator": 50,
}

NON_PERSON_PATTERNS = [
    r"customer service", r"support team", r"dispatch desk", r"sales department",
    r"info", r"admin", r"contact us", r"billing", r"recruiting", r"careers",
    r"trucking", r"freight", r"logistics", r"express", r"transport"
]

class DecisionMakerFinder:
    """Extracts, ranks, and verifies genuine decision makers without fabrication."""

    @classmethod
    def is_valid_person_name(cls, name: Optional[str]) -> bool:
        """Ensures extracted text is a plausible human name and not a generic department/company name."""
        if not name:
            return False
        clean = name.strip()
        if len(clean) < 3 or len(clean.split()) < 2:
            return False
        # Check against blacklist
        clean_lower = clean.lower()
        for pat in NON_PERSON_PATTERNS:
            if re.search(pat, clean_lower):
                return False
        # Must contain alphabetical characters
        if not re.match(r"^[a-zA-Z\s\.\-']+$", clean):
            return False
        return True

    @classmethod
    def get_title_rank(cls, title: Optional[str]) -> int:
        """Returns integer ranking for title (higher = more senior decision maker)."""
        if not title:
            return 0
        title_lower = title.lower().strip()
        for key, rank in DM_TITLE_RANKINGS.items():
            if key in title_lower:
                return rank
        return 10

    @classmethod
    def identify_primary_decision_maker(cls, contacts: List[Contact]) -> Tuple[Optional[Contact], float]:
        """
        Evaluates contacts and returns the highest-ranking genuine decision maker
        along with detection confidence score.
        """
        if not contacts:
            return None, 0.0

        best_contact = None
        highest_rank = 0

        for contact in contacts:
            if not cls.is_valid_person_name(contact.full_name):
                continue

            rank = cls.get_title_rank(contact.title)
            # Boost if verified email or phone is attached
            confidence_boost = 0.1 if (contact.email or contact.phone) else 0.0

            if rank > highest_rank:
                highest_rank = rank
                best_contact = contact
                contact.is_decision_maker = True
                contact.confidence = min(1.0, (rank / 100.0) + confidence_boost)

        if best_contact:
            return best_contact, best_contact.confidence

        return None, 0.0

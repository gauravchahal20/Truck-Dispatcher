import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..models.entities import IntentSignal
from ..core.config import config

INTENT_RULES = {
    "HIRING_DISPATCH": [
        r"hiring (?:a )?(?:[a-z0-9\-]+ )*(?:truck |freight |night )?dispatch(?:er|ers)?",
        r"seeking (?:a )?(?:[a-z0-9\-]+ )*dispatcher",
        r"dispatch coordinator needed",
        r"dispatch supervisor",
        r"load planner wanted",
        r"freight coordinator hiring"
    ],
    "HIRING_FLEET_MGR": [
        r"hiring (?:a )?(?:[a-z0-9\-]+ )*fleet manager",
        r"fleet manager wanted",
        r"transportation coordinator needed",
        r"logistics coordinator job",
        r"director of safety and fleet"
    ],
    "FLEET_EXPANSION": [
        r"adding (?:new )?trucks",
        r"(?:added|purchased|bought|acquired|leased) \d+ (?:new )?(?:tractors|trucks|rigs|trailers|units)",
        r"fleet expansion",
        r"expanding (?:rapidly|our freight operations|our fleet)",
        r"purchased (?:new )?(?:tractors|rigs|trailers)",
        r"leased \d+ (?:new )?units",
        r"opening (?:a )?new terminal",
        r"growing our fleet"
    ],
    "PUBLIC_DISPATCH_REQUEST": [
        r"looking for (?:a )?(?:reliable )?dispatch service",
        r"need dispatch help",
        r"for hire carrier seeking freight",
        r"open for dispatch partnership",
        r"need load booking service"
    ],
    "AWARDS_CONTRACTS": [
        r"awarded (?:new )?freight contract",
        r"government transportation contract",
        r"dod freight carrier award",
        r"logistics partner of the year",
        r"secured dedicated lane contract"
    ],
    "TECH_ADOPTION": [
        r"implementing new tms",
        r"samsara",
        r"motive eld",
        r"keep trucking",
        r"telematics upgrade",
        r"automated dispatch software"
    ]
}

class IntentAnalyzer:
    """Detects and scores business intent signals from job postings, news, and web text."""

    @classmethod
    def analyze_text(
        cls,
        text: Optional[str],
        source_url: Optional[str] = None,
        source_name: str = "web"
    ) -> List[IntentSignal]:
        """
        Scans raw text against trucking intent signals.
        Returns a list of detected IntentSignal entity instances.
        """
        if not text:
            return []

        detected_signals: List[IntentSignal] = []
        text_lower = text.lower()

        for signal_type, patterns in INTENT_RULES.items():
            for pat in patterns:
                match = re.search(pat, text_lower)
                if match:
                    # Extract surrounding context snippet (120 chars)
                    start = max(0, match.start() - 40)
                    end = min(len(text), match.end() + 80)
                    snippet = text[start:end].strip().replace("\n", " ")

                    # Calculate confidence based on source & match precision
                    confidence = 0.85 if source_name in ("indeed", "google_news") else 0.70

                    signal = IntentSignal(
                        signal_type=signal_type,
                        title=f"{signal_type.replace('_', ' ').title()}: '{match.group(0)}'",
                        description=snippet,
                        source_url=source_url,
                        confidence=confidence,
                        detected_date=datetime.now(timezone.utc)
                    )
                    detected_signals.append(signal)
                    break  # Avoid multiple duplicate matches for same category in same text

        return detected_signals

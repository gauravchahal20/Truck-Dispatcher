import math
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from ..core.config import config
from ..models.entities import Company, IntentSignal, FMCSACarrierCensus, FMCSAInsurance

logger = logging.getLogger("trucklead.signal_engine")


class SignalEngine:
    """
    Signal Engine v1:
    - Typed signals with config-driven exponential half-life time decay
    - Separation of fit_score and intent_score
    - Flags sensitive insurance cancellation signals for qualification only
    """

    @classmethod
    def calculate_decayed_strength(
        cls,
        initial_strength: float,
        observed_at: datetime,
        current_time: Optional[datetime] = None,
        half_life_days: float = 60.0
    ) -> float:
        """
        Calculates time-decayed strength using exponential half-life formula:
        S(t) = S0 * 2^(-Delta_t / t_half)
        """
        if initial_strength <= 0.0 or half_life_days <= 0.0:
            return 0.0

        now = current_time or datetime.now(timezone.utc)
        # Ensure timezone-awareness
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        delta_seconds = (now - observed_at).total_seconds()
        delta_days = max(0.0, delta_seconds / 86400.0)

        # Exponential decay: 2^(-delta_days / half_life_days)
        decay_factor = math.pow(0.5, delta_days / half_life_days)
        return round(initial_strength * decay_factor, 4)

    @classmethod
    def parse_fmcsa_date(cls, date_val: Optional[str]) -> Optional[datetime]:
        """Parses FMCSA date strings (YYYYMMDD, MM/DD/YYYY, or ISO YYYY-MM-DD)."""
        if not date_val:
            return None
        s = str(date_val).strip()
        if not s or s.lower() == "none" or s.lower() == "null":
            return None

        for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @classmethod
    def detect_signals(
        cls,
        company: Company,
        census_record: Optional[FMCSACarrierCensus] = None,
        insurance_records: Optional[List[FMCSAInsurance]] = None,
        current_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts typed signals with config-driven parameters:
        1. NEW_AUTHORITY: Granted in last 30-120 days
        2. INSURANCE_CANCEL_PENDING: Carrier has a pending insurance cancellation filing (SENSITIVE)
        3. MCS150_RECENT_UPDATE: Biennial update within recent window
        4. POWER_UNITS_GROWTH: Fleet growth detected between snapshots
        """
        engine_cfg = getattr(getattr(config, "signals", None), "engine", None)
        hl_cfg = getattr(engine_cfg, "half_life_days", None) if engine_cfg else None

        now = current_time or datetime.now(timezone.utc)
        detected: List[Dict[str, Any]] = []

        if company.lead_type != "CARRIER":
            return detected

        # 1. NEW_AUTHORITY (Granted in last 30-120 days)
        add_date_str = getattr(census_record, "add_date", None)
        add_dt = cls.parse_fmcsa_date(add_date_str)
        if add_dt:
            age_days = (now - add_dt).total_seconds() / 86400.0
            win_min = getattr(getattr(engine_cfg, "new_authority_window", None), "min_days", 30)
            win_max = getattr(getattr(engine_cfg, "new_authority_window", None), "max_days", 120)
            if win_min <= age_days <= win_max:
                detected.append({
                    "signal_type": "NEW_AUTHORITY",
                    "title": f"Newly Granted Operating Authority ({int(age_days)} days ago)",
                    "description": f"Carrier FMCSA authority granted on {add_date_str} within the target 30-120 day growth window.",
                    "source_url": "https://data.transportation.gov/resource/az4n-8mr2",
                    "confidence": 0.95,
                    "strength": 1.0,
                    "observed_at": add_dt,
                    "half_life_days": getattr(hl_cfg, "new_authority", 45.0),
                    "evidence": {
                        "dataset_id": "az4n-8mr2",
                        "row_reference": {"dot_number": company.usdot, "add_date": add_date_str}
                    },
                    "is_sensitive": False
                })

        # 2. INSURANCE_CANCEL_PENDING (Pending cancellation filing)
        # SENSITIVE: Flagged for qualification only, strictly prohibited for manipulative messaging
        ins_recs = insurance_records or []
        for ins in ins_recs:
            cancl_str = getattr(ins, "cancl_effective_date", None)
            if cancl_str:
                cancl_dt = cls.parse_fmcsa_date(cancl_str)
                obs_dt = cancl_dt or now
                detected.append({
                    "signal_type": "INSURANCE_CANCEL_PENDING",
                    "title": "Pending Insurance Cancellation Notice",
                    "description": f"Carrier has a pending policy cancellation effective {cancl_str} (Insurer: {getattr(ins, 'name_company', 'Unknown')}).",
                    "source_url": "https://data.transportation.gov/resource/qh9u-swkp",
                    "confidence": 0.90,
                    "strength": 1.0,
                    "observed_at": obs_dt,
                    "half_life_days": getattr(hl_cfg, "insurance_cancel_pending", 15.0),
                    "evidence": {
                        "dataset_id": "qh9u-swkp",
                        "row_reference": {
                            "dot_number": company.usdot,
                            "policy_no": getattr(ins, "policy_no", None),
                            "cancl_effective_date": cancl_str
                        }
                    },
                    "is_sensitive": True  # Sensitive: for qualification only, not for outreach messaging
                })
                break

        # 3. MCS150_RECENT_UPDATE (Updated within recent window, e.g. 60 days)
        mcs_date_str = company.mcs_150_date or getattr(census_record, "mcs150_date", None)
        mcs_dt = cls.parse_fmcsa_date(mcs_date_str)
        if mcs_dt:
            age_days = (now - mcs_dt).total_seconds() / 86400.0
            mcs_win = getattr(engine_cfg, "mcs150_window_days", 60)
            if 0 <= age_days <= mcs_win:
                detected.append({
                    "signal_type": "MCS150_RECENT_UPDATE",
                    "title": f"Recent MCS-150 Biennial Update ({int(age_days)} days ago)",
                    "description": f"Carrier filed an updated MCS-150 registration on {mcs_date_str}.",
                    "source_url": "https://data.transportation.gov/resource/az4n-8mr2",
                    "confidence": 0.85,
                    "strength": 1.0,
                    "observed_at": mcs_dt,
                    "half_life_days": getattr(hl_cfg, "mcs150_recent_update", 60.0),
                    "evidence": {
                        "dataset_id": "az4n-8mr2",
                        "row_reference": {"dot_number": company.usdot, "mcs150_date": mcs_date_str}
                    },
                    "is_sensitive": False
                })

        # 4. POWER_UNITS_GROWTH (Compare snapshots or noted expansions)
        notes = (company.notes or "").lower()
        if "fleet growth" in notes or "adding trucks" in notes or "fleet expansion" in notes:
            detected.append({
                "signal_type": "POWER_UNITS_GROWTH",
                "title": "Carrier Fleet Expansion Detected",
                "description": "Carrier increased active power units or posted fleet expansion indicators.",
                "source_url": "https://data.transportation.gov/resource/az4n-8mr2",
                "confidence": 0.80,
                "strength": 1.0,
                "observed_at": now - timedelta(days=10),
                "half_life_days": getattr(hl_cfg, "power_units_growth", 90.0),
                "evidence": {
                    "dataset_id": "az4n-8mr2",
                    "row_reference": {"dot_number": company.usdot, "metric": "power_units_increase"}
                },
                "is_sensitive": False
            })

        # 5. NEW_USDOT_REGISTRATION (Fresh DOT assignment / registration within 60 days)
        if getattr(company, "lead_source", None) == "recent_registration" or "recent_registration" in notes:
            reg_dt = add_dt or now
            detected.append({
                "signal_type": "NEW_USDOT_REGISTRATION",
                "title": "Fresh USDOT Registration",
                "description": "Carrier completed recent initial USDOT registration.",
                "source_url": "https://data.transportation.gov/resource/az4n-8mr2",
                "confidence": 0.90,
                "strength": 1.0,
                "observed_at": reg_dt,
                "half_life_days": getattr(hl_cfg, "new_usdot_registration", 60.0),
                "evidence": {
                    "dataset_id": "az4n-8mr2",
                    "row_reference": {"dot_number": company.usdot, "segment": "recent_registration"}
                },
                "is_sensitive": False
            })

        # 6. PENDING_AUTHORITY (Form OP-1 application pending; not yet operating)
        if getattr(company, "segment", None) == "pending_authority" or "not yet operating" in notes:
            detected.append({
                "signal_type": "PENDING_AUTHORITY",
                "title": "Pending Operating Authority Application",
                "description": "Carrier filed Form OP-1 operating authority application awaiting grant (not yet operating).",
                "source_url": "https://data.transportation.gov/resource/inys-ebih",
                "confidence": 0.85,
                "strength": 1.0,
                "observed_at": now,
                "half_life_days": getattr(hl_cfg, "pending_authority", 90.0),
                "evidence": {
                    "dataset_id": "inys-ebih",
                    "row_reference": {"dot_number": company.usdot, "segment": "pending_authority", "flag": "not yet operating"}
                },
                "is_sensitive": False
            })

        return detected

    @classmethod
    def calculate_intent_score(
        cls,
        signals: List[IntentSignal],
        current_time: Optional[datetime] = None
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculates total intent points from active decayed signals.
        If no signals present -> returns 0.0 intent points (strict requirement).
        Decayed strength scales signal point contribution toward zero as time elapses.
        """
        if not signals or len(signals) == 0:
            return 0.0, []

        engine_cfg = getattr(getattr(config, "signals", None), "engine", None)
        weights_cfg = getattr(engine_cfg, "weights", None) if engine_cfg else None
        max_intent = getattr(engine_cfg, "max_intent_points", 3.0)

        now = current_time or datetime.now(timezone.utc)
        total_intent = 0.0
        breakdown = []

        for sig in signals:
            sig_type = (sig.signal_type or "").upper()
            observed = sig.observed_at or sig.detected_date or now
            half_life = sig.half_life_days or 60.0
            initial_strength = sig.strength if sig.strength is not None else 1.0

            # 1. Exponential Decay Calculation
            decayed = cls.calculate_decayed_strength(
                initial_strength=initial_strength,
                observed_at=observed,
                current_time=now,
                half_life_days=half_life
            )

            # 2. Get signal weight
            if "NEW_AUTHORITY" in sig_type:
                w = getattr(weights_cfg, "new_authority", 2.0)
            elif "NEW_USDOT_REGISTRATION" in sig_type or "REGISTRATION" in sig_type:
                w = getattr(weights_cfg, "new_usdot_registration", 0.5)
            elif "PENDING_AUTHORITY" in sig_type or "PENDING" in sig_type:
                w = getattr(weights_cfg, "pending_authority", 0.5)
            elif "INSURANCE_CANCEL" in sig_type:
                w = getattr(weights_cfg, "insurance_cancel_pending", 1.5)
            elif "MCS150" in sig_type:
                w = getattr(weights_cfg, "mcs150_recent_update", 1.0)
            elif "POWER_UNITS" in sig_type or "EXPANSION" in sig_type:
                w = getattr(weights_cfg, "power_units_growth", 1.5)
            else:
                w = getattr(weights_cfg, "generic_intent", 1.0)

            earned = round(w * decayed, 2)
            total_intent += earned

            breakdown.append({
                "type": sig.signal_type,
                "title": sig.title,
                "initial_strength": initial_strength,
                "decayed_strength": decayed,
                "weight": w,
                "points_earned": earned,
                "is_sensitive": getattr(sig, "is_sensitive", False),
                "evidence": getattr(sig, "evidence", {})
            })

        capped_intent = round(min(max_intent, total_intent), 1)
        return capped_intent, breakdown

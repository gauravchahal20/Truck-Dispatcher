"""
FMCSA Motus Aggregator Service.
Reduces multiple raw rows from FMCSA Motus (inys-ebih) for a given USDOT
into a single authoritative operating authority and insurance status.

Aggregation Rules:
1. Target: Motor Carrier of Property only (Except Household Goods).
   - Excludes broker-only, freight forwarder-only, and passenger-only filings from motor carrier authority.
2. Docket & Authority Resolution:
   - When multiple filings exist, property carrier filings take precedence.
   - Status resolution hierarchy: Active > Pending > Withdrawn / Revoked / Inactive.
3. Insurance BIPD Validation:
   - BIPD filing >= $750,000 required for freight property carriers (ACTIVE).
   - BIPD > $0 but < $750,000 flagged as PARTIAL.
   - BIPD == 0 or missing flagged as NONE.
4. Absence of Records:
   - If 0 rows exist in Motus, returns NO_LI_RECORD (neither active nor revoked; unverified L&I).
"""
from typing import List, Dict, Any, Optional

PROPERTY_AUTH_TYPE = "Motor Carrier of Property (Except Household Goods)"

class MotusAggregator:
    @staticmethod
    def aggregate(rows: List[Dict[str, Any]], usdot: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate multiple Motus rows for a USDOT into a single unified record.
        """
        if not rows:
            return {
                "usdot": usdot,
                "docket_number": None,
                "op_auth_type": None,
                "raw_op_auth_status": None,
                "authority_status": "NO_LI_RECORD",
                "insurance_status": "NONE",
                "bipd_amount": 0.0,
                "is_active_property_carrier": False,
                "is_active_for_hire": False,
                "notes": "No filing records in inys-ebih master licensing & insurance database"
            }

        # Filter rows by authority type
        property_rows = []
        other_carrier_rows = []
        broker_forwarder_rows = []

        for r in rows:
            atype = (r.get("op_auth_type") or "").strip()
            if atype == PROPERTY_AUTH_TYPE:
                property_rows.append(r)
            elif "Motor Carrier" in atype:
                other_carrier_rows.append(r)
            elif "Broker" in atype or "Freight Forwarder" in atype:
                broker_forwarder_rows.append(r)

        # Hierarchy for picking the governing record
        selected_row = None
        target_pool = property_rows or other_carrier_rows

        if target_pool:
            # Sort order: Active > Pending > Inactive > Withdrawn / Revoked
            status_priority = {
                "Active": 4,
                "Pending": 3,
                "Inactive": 2,
                "Withdrawn": 1,
                "Revoked": 1
            }
            # Pick highest priority, and highest BIPD if tied
            def sort_key(row):
                st = row.get("op_auth_status") or ""
                bipd_str = row.get("bipd_file") or "0"
                try:
                    bipd = float(bipd_str)
                except ValueError:
                    bipd = 0.0
                return (status_priority.get(st, 0), bipd)

            selected_row = max(target_pool, key=sort_key)
            is_property = (selected_row in property_rows)
        elif broker_forwarder_rows:
            # Only broker/forwarder filings exist - cannot operate as motor carrier of property
            selected_row = broker_forwarder_rows[0]
            is_property = False
        else:
            selected_row = rows[0]
            is_property = False

        raw_status = (selected_row.get("op_auth_status") or "").strip()
        auth_type = (selected_row.get("op_auth_type") or "").strip()
        docket = selected_row.get("docket_number")
        usdot_resolved = str(selected_row.get("usdot_number") or usdot or "")

        # Parse BIPD
        bipd_str = selected_row.get("bipd_file") or "0"
        try:
            bipd_amount = float(bipd_str)
        except ValueError:
            bipd_amount = 0.0

        if bipd_amount >= 750000.0:
            insurance_status = "ACTIVE"
        elif bipd_amount > 0.0:
            insurance_status = "PARTIAL"
        else:
            insurance_status = "NONE"

        # Determine authority_status
        if not is_property and not target_pool:
            authority_status = "NO_PROPERTY_AUTHORITY"
        else:
            if raw_status.lower() == "active":
                authority_status = "ACTIVE"
            elif raw_status.lower() == "pending":
                authority_status = "PENDING"
            elif raw_status.lower() in ("withdrawn", "revoked", "inactive"):
                authority_status = raw_status.upper()
            else:
                authority_status = "UNKNOWN"

        is_active_for_hire = (authority_status == "ACTIVE" and insurance_status == "ACTIVE")

        return {
            "usdot": usdot_resolved,
            "docket_number": docket,
            "op_auth_type": auth_type,
            "raw_op_auth_status": raw_status,
            "authority_status": authority_status,
            "insurance_status": insurance_status,
            "bipd_amount": bipd_amount,
            "is_active_property_carrier": is_property and (authority_status == "ACTIVE"),
            "is_active_for_hire": is_active_for_hire,
            "notes": f"Aggregated from {len(rows)} raw Motus filing(s)"
        }

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Run, Company, Contact, SourceRecord, VerificationRecord, IntentSignal, ErrorLog
from ..core.config import config, settings, PROJECT_ROOT

logger = logging.getLogger("trucklead.sheets")

FINAL_LEADS_HEADERS = [
    "Company", "Legal Name", "Website", "City", "State", "USDOT", "Fleet Size", "Equipment",
    "Decision Maker", "Title", "Business Email", "Business Phone", "LinkedIn",
    "Lead Source", "Source URL", "Intent Signal", "Intent Source", "Qualification Reason",
    "Lead Score", "Priority", "Verification Status", "Verification Confidence",
    "Verification Date", "Created Date", "Notes"
]

RUN_REPORT_HEADERS = [
    "Run ID", "Date", "Target", "Raw Leads", "Verified", "Qualified", "Final", "Rejected",
    "Duplicates", "A Leads", "B Leads", "Source Counts", "Errors"
]

class GoogleSheetsService:
    """Synchronizes verified lead batches to Google Sheets and generates local XLSX/CSV backups."""

    def __init__(self):
        raw_dir = Path(config.sheets.backup_dir)
        self.backup_dir = raw_dir if raw_dir.is_absolute() else (PROJECT_ROOT / raw_dir).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)


    def _get_gspread_client(self):
        """Initializes gspread client if credentials exist."""
        try:
            import gspread
            # Check 1: Raw JSON string in env
            if settings.google_service_account_json:
                creds_dict = json.loads(settings.google_service_account_json)
                return gspread.service_account_from_dict(creds_dict)
            # Check 2: File path in env
            if settings.google_application_credentials and Path(settings.google_application_credentials).is_file():
                return gspread.service_account(filename=settings.google_application_credentials)
            # Check 3: Standard GCP path
            default_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if default_path and Path(default_path).is_file():
                return gspread.service_account(filename=default_path)
        except Exception as e:
            logger.warning(f"Google Sheets authentication not configured: {e}")
        return None

    async def sync_run_to_sheets(self, session: AsyncSession, run: Run) -> Dict[str, Any]:
        """
        Gathers all companies and logs for a run, exports local CSV/Excel backups,
        and pushes rows to Google Sheets if configured.
        """
        # Load run with all related entities
        query = (
            select(Company)
            .where(Company.run_id == run.id)
            .options(
                selectinload(Company.contacts),
                selectinload(Company.sources),
                selectinload(Company.intent_signals),
                selectinload(Company.verification_records),
                selectinload(Company.lead_score_detail)
            )
        )
        result = await session.execute(query)
        companies = result.scalars().all()

        final_rows = []
        queue_rows = []
        rejected_rows = []
        source_rows = []

        for c in companies:
            # 1. Decision maker
            dm_contact = next((ct for ct in c.contacts if ct.is_decision_maker), None)
            dm_name = dm_contact.full_name if dm_contact else (c.contacts[0].full_name if c.contacts else "UNKNOWN")
            dm_title = dm_contact.title if dm_contact else (c.contacts[0].title if c.contacts else "UNKNOWN")
            dm_email = dm_contact.email if dm_contact and dm_contact.email else (c.email or "UNKNOWN")
            dm_phone = dm_contact.phone if dm_contact and dm_contact.phone else (c.phone or "UNKNOWN")
            dm_linkedin = dm_contact.linkedin_url if dm_contact and dm_contact.linkedin_url else "UNKNOWN"

            # 2. Intent signal
            primary_intent = c.intent_signals[0] if c.intent_signals else None
            intent_sig_text = primary_intent.title if primary_intent else "None"
            intent_sig_url = primary_intent.source_url if primary_intent else ""

            # Equipment formatted string
            equipment_str = ", ".join(c.equipment) if c.equipment else "Unknown"

            # Format Dates
            v_date = c.verification_date.strftime("%Y-%m-%d") if c.verification_date else ""
            c_date = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""

            # 1. FINAL LEADS
            if c.lead_status == "FINAL":
                row = [
                    c.company_name or "",
                    c.legal_name or c.company_name or "",
                    c.website or "",
                    c.city or "",
                    c.state or "",
                    c.usdot or "",
                    c.fleet_size if c.fleet_size is not None else "",
                    equipment_str,
                    dm_name,
                    dm_title,
                    dm_email,
                    dm_phone,
                    dm_linkedin,
                    c.lead_source or "",
                    c.source_url or "",
                    intent_sig_text,
                    intent_sig_url,
                    c.qualification_reason or f"Score: {c.lead_score} (Priority {c.priority})",
                    c.lead_score,
                    c.priority or "B",
                    c.verification_status,
                    f"{c.verification_confidence * 100:.0f}%" if c.verification_confidence else "0%",
                    v_date,
                    c_date,
                    c.notes or ""
                ]
                final_rows.append(row)

            # 2. RESEARCH QUEUE
            elif c.lead_status in ("RAW", "RESEARCHING", "ENRICHED", "NEEDS_REVIEW"):
                queue_rows.append([
                    c.company_name,
                    c.usdot or "N/A",
                    c.state or "N/A",
                    c.lead_status,
                    c.lead_source or "N/A",
                    c_date,
                    c.notes or ""
                ])

            # 3. REJECTED
            elif c.lead_status == "REJECTED":
                rejected_rows.append([
                    c.company_name,
                    c.usdot or "N/A",
                    c.state or "N/A",
                    c.fleet_size if c.fleet_size is not None else "N/A",
                    c.rejection_reason or "Below qualification threshold",
                    c.lead_score,
                    c_date
                ])

            # 4. SOURCE LOG
            for s in c.sources:
                source_rows.append([
                    run.id,
                    c.company_name,
                    s.source_name,
                    s.source_url or "",
                    s.discovered_at.strftime("%Y-%m-%d %H:%M") if s.discovered_at else "",
                    f"{s.extraction_confidence * 100:.0f}%"
                ])

        # 5. RUN REPORT
        target_str = f"States: {', '.join(run.target_states or [])} | Fleet: {run.fleet_size_min}-{run.fleet_size_max}"
        run_date_str = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        source_counts_str = json.dumps(run.source_counts or {})

        report_row = [
            run.id,
            run_date_str,
            target_str,
            run.raw_count,
            run.verified_count,
            run.qualified_count,
            run.final_count,
            run.rejected_count,
            run.duplicate_count,
            run.priority_a_count,
            run.priority_b_count,
            source_counts_str,
            run.error_count
        ]

        # Export Local XLSX Backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_path = self.backup_dir / f"run_{run.id[:8]}_{timestamp}.xlsx"
        csv_path = self.backup_dir / f"final_leads_{run.id[:8]}_{timestamp}.csv"

        try:
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                pd.DataFrame(final_rows, columns=FINAL_LEADS_HEADERS).to_excel(writer, sheet_name=config.sheets.tabs["final_leads"], index=False)
                pd.DataFrame(queue_rows, columns=["Company", "USDOT", "State", "Status", "Source", "Date", "Notes"]).to_excel(writer, sheet_name=config.sheets.tabs["research_queue"], index=False)
                pd.DataFrame(rejected_rows, columns=["Company", "USDOT", "State", "Fleet Size", "Reason", "Score", "Date"]).to_excel(writer, sheet_name=config.sheets.tabs["rejected"], index=False)
                pd.DataFrame(source_rows, columns=["Run ID", "Company", "Source", "URL", "Date", "Confidence"]).to_excel(writer, sheet_name=config.sheets.tabs["source_log"], index=False)
                pd.DataFrame([report_row], columns=RUN_REPORT_HEADERS).to_excel(writer, sheet_name=config.sheets.tabs["run_report"], index=False)

            # Export standalone CSV of final leads
            pd.DataFrame(final_rows, columns=FINAL_LEADS_HEADERS).to_csv(csv_path, index=False)

            run.export_xlsx_path = str(xlsx_path)
            run.export_csv_path = str(csv_path)
            logger.info(f"Local lead reports exported to: {xlsx_path} and {csv_path}")
        except Exception as e:
            logger.error(f"Failed to generate local Excel/CSV backup: {e}")

        # Sync to Google Sheets if client and sheet ID available
        sheet_sync_status = "LOCAL_ONLY"
        spreadsheet_url = None
        gc = self._get_gspread_client()
        sheet_id = config.sheets.spreadsheet_id or settings.google_spreadsheet_id

        if gc and sheet_id:
            try:
                sh = gc.open_by_key(sheet_id)
                # Tab 1: FINAL_LEADS
                ws_final = self._get_or_create_worksheet(sh, config.sheets.tabs["final_leads"], FINAL_LEADS_HEADERS)
                if final_rows:
                    ws_final.append_rows(final_rows)

                # Tab 2: RESEARCH_QUEUE
                ws_queue = self._get_or_create_worksheet(sh, config.sheets.tabs["research_queue"], ["Company", "USDOT", "State", "Status", "Source", "Date", "Notes"])
                if queue_rows:
                    ws_queue.append_rows(queue_rows)

                # Tab 3: REJECTED
                ws_rej = self._get_or_create_worksheet(sh, config.sheets.tabs["rejected"], ["Company", "USDOT", "State", "Fleet Size", "Reason", "Score", "Date"])
                if rejected_rows:
                    ws_rej.append_rows(rejected_rows)

                # Tab 4: SOURCE_LOG
                ws_src = self._get_or_create_worksheet(sh, config.sheets.tabs["source_log"], ["Run ID", "Company", "Source", "URL", "Date", "Confidence"])
                if source_rows:
                    ws_src.append_rows(source_rows)

                # Tab 5: RUN_REPORT
                ws_rep = self._get_or_create_worksheet(sh, config.sheets.tabs["run_report"], RUN_REPORT_HEADERS)
                ws_rep.append_row(report_row)

                spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
                run.google_sheet_url = spreadsheet_url
                sheet_sync_status = "SYNCED_TO_GOOGLE_SHEETS"
                logger.info(f"Successfully synced lead batch to Google Sheets: {spreadsheet_url}")
            except Exception as e:
                logger.error(f"Google Sheets sync failed: {e}")
                sheet_sync_status = f"SYNC_ERROR: {e}"

        return {
            "status": sheet_sync_status,
            "spreadsheet_url": spreadsheet_url,
            "xlsx_path": str(xlsx_path),
            "csv_path": str(csv_path),
            "final_count": len(final_rows),
            "rejected_count": len(rejected_rows),
            "queue_count": len(queue_rows)
        }

    def _get_or_create_worksheet(self, spreadsheet, title: str, headers: List[str]):
        """Retrieves or creates a worksheet with standardized header row."""
        try:
            ws = spreadsheet.worksheet(title)
        except Exception:
            ws = spreadsheet.add_worksheet(title=title, rows=500, cols=len(headers) + 2)
            ws.append_row(headers)
        return ws

sheets_service = GoogleSheetsService()

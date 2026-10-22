from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..core.config import config, settings
from ..models.entities import Run
from ..services.sheets_service import sheets_service

router = APIRouter(prefix="/api/sheets", tags=["Google Sheets"])


@router.get("/status")
async def get_sheets_status() -> Dict[str, Any]:
    """Checks Google Sheets integration status and active spreadsheet ID."""
    has_creds = bool(
        settings.google_service_account_json or
        settings.google_application_credentials or
        sheets_service._get_gspread_client() is not None
    )
    sheet_id = config.sheets.spreadsheet_id or settings.google_spreadsheet_id

    return {
        "enabled": config.sheets.enabled,
        "credentials_configured": has_creds,
        "spreadsheet_id": sheet_id or "NOT_CONFIGURED",
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else None,
        "backup_directory": str(sheets_service.backup_dir),
        "export_local_backup_xlsx": config.sheets.export_local_backup_xlsx,
        "export_local_backup_csv": config.sheets.export_local_backup_csv
    }


from pydantic import BaseModel
from typing import Optional

class SyncRequest(BaseModel):
    run_id: Optional[str] = None


@router.post("/sync")
@router.post("/sync/{run_id}")
async def force_sync_run(
    run_id: Optional[str] = None,
    req: Optional[SyncRequest] = None,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Manually triggers Google Sheets sync and re-exports files for a specific run or latest completed run."""
    target_id = run_id or (req.run_id if req else None)
    if target_id:
        run = await session.get(Run, target_id)
    else:
        from sqlalchemy import desc, select
        query = select(Run).order_by(desc(Run.created_at)).limit(1)
        res = await session.execute(query)
        run = res.scalars().first()

    if not run:
        raise HTTPException(status_code=404, detail="No run found to sync")

    result = await sheets_service.sync_run_to_sheets(session, run)
    await session.commit()
    return result

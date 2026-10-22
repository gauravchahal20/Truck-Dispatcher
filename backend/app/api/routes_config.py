from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..core.config import config

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("")
async def get_system_config() -> Dict[str, Any]:
    """Returns active runtime configuration."""
    yaml_text = ""
    config_file = config.config_file_path
    if config_file and Path(config_file).is_file():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                yaml_text = f.read()
        except Exception as e:
            yaml_text = f"# Failed to read config file: {e}"

    return {
        "yaml_content": yaml_text,
        "icp": config.icp.model_dump(),
        "scoring": config.scoring.model_dump(),
        "budget": config.budget.model_dump(),
        "security": config.security.model_dump(),
        "sheets": config.sheets.model_dump(),
        "decision_makers": config.decision_makers,
        "sources": {k: v.model_dump() for k, v in config.sources.items()}
    }


class ConfigUpdateRequest(BaseModel):
    yaml_content: Optional[str] = None
    target_states: Optional[List[str]] = None
    fleet_min: Optional[int] = None
    fleet_max: Optional[int] = None
    score_threshold: Optional[float] = None
    spreadsheet_id: Optional[str] = None


@router.put("")
async def update_system_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Updates runtime configuration settings from YAML or structured JSON."""
    if "yaml_content" in payload and payload["yaml_content"]:
        yaml_content = payload["yaml_content"]
        try:
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                raise HTTPException(status_code=400, detail="YAML must be a valid mapping dictionary.")
        except yaml.YAMLError as ye:
            raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {ye}")

        config_file = config.config_file_path
        if config_file:
            try:
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write(yaml_content)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to write config file: {e}")

        # Reload runtime config singleton
        config.reload()

    if "icp" in payload:
        icp_data = payload["icp"]
        if "target_states" in icp_data:
            config.icp.target_states = icp_data["target_states"]
        if "fleet_size" in icp_data:
            if "min" in icp_data["fleet_size"]:
                config.icp.fleet_size.min = icp_data["fleet_size"]["min"]
            if "max" in icp_data["fleet_size"]:
                config.icp.fleet_size.max = icp_data["fleet_size"]["max"]
        if "score_threshold_for_final" in icp_data:
            config.icp.score_threshold_for_final = icp_data["score_threshold_for_final"]

    if "sheets" in payload and "spreadsheet_id" in payload["sheets"]:
        config.sheets.spreadsheet_id = payload["sheets"]["spreadsheet_id"]

    return await get_system_config()


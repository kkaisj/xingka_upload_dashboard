from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...services.brand_profile_service import apply_brand_profile, load_brand_profiles, save_brand_profiles
from ...services.global_config_service import GLOBAL_CONFIG_KEYS, load_global_config, parse_accounts, save_global_config
from ...services.rpa_console import ConsoleService

router = APIRouter(prefix="/config", tags=["config"])


class SaveConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    restart_scheduler: bool = True


class RobotStatusRequest(BaseModel):
    accounts: Optional[list[str]] = None


class SaveBrandProfilesRequest(BaseModel):
    profiles: dict[str, dict[str, list[str]]] = Field(default_factory=dict)


class ApplyBrandProfileRequest(BaseModel):
    brand: str
    reset_progress: bool = False


@router.get("/global")
def get_global_config() -> dict[str, Any]:
    settings = get_settings()
    return {"config": load_global_config(settings.root_dir), "keys": GLOBAL_CONFIG_KEYS}


@router.put("/global")
def put_global_config(req: SaveConfigRequest, request: Request) -> dict[str, Any]:
    settings = get_settings()
    saved = save_global_config(settings.root_dir, req.config)

    restarted = False
    status: dict[str, Any] = {"enabled": False, "running": False, "thread_name": None, "last_error": ""}
    if req.restart_scheduler:
        service = getattr(request.app.state, "scheduler_service", None)
        if service is not None:
            service.stop(timeout_seconds=10.0)
            started = service.start()
            restarted = bool(started)
            status = service.status_dict()

    return {
        "ok": True,
        "config": saved,
        "restart_scheduler": req.restart_scheduler,
        "restarted": restarted,
        "scheduler_status": status,
    }


@router.get("/brand-profiles")
def get_brand_profiles() -> dict[str, Any]:
    settings = get_settings()
    return {"profiles": load_brand_profiles(settings.root_dir)}


@router.put("/brand-profiles")
def put_brand_profiles(req: SaveBrandProfilesRequest) -> dict[str, Any]:
    settings = get_settings()
    return {"ok": True, "profiles": save_brand_profiles(settings.root_dir, req.profiles)}


@router.post("/apply-brand-profile")
def post_apply_brand_profile(req: ApplyBrandProfileRequest) -> dict[str, Any]:
    settings = get_settings()
    result = apply_brand_profile(
        settings.root_dir,
        req.brand,
        reset_progress=req.reset_progress,
        state_path=settings.state_file,
    )
    result["ok"] = True
    return result


@router.get("/robots/list")
def robots_list() -> dict[str, Any]:
    console = ConsoleService()
    rows = console.robot_list(page=1, size=100)
    out = []
    for r in rows:
        out.append(
            {
                "robotClientUuid": r.get("robotClientUuid"),
                "robotClientName": r.get("robotClientName"),
                "status": r.get("status"),
                "description": r.get("description"),
                "windowsUserName": r.get("windowsUserName"),
                "clientIp": r.get("clientIp"),
                "machineName": r.get("machineName"),
                "accountName": r.get("robotClientName"),
            }
        )
    return {"robots": out, "total": len(out)}


@router.post("/robots/status")
def robots_status(req: RobotStatusRequest) -> dict[str, Any]:
    settings = get_settings()
    cfg = load_global_config(settings.root_dir)
    accounts = req.accounts if req.accounts else parse_accounts(cfg.get("ACCOUNT_NAMES", ""))
    if not accounts:
        raise HTTPException(status_code=400, detail="ACCOUNT_NAMES is empty")

    console = ConsoleService()
    rows: list[dict[str, Any]] = []
    for account in accounts:
        try:
            data = console.robot_status(account)
            rows.append(
                {
                    "accountName": account,
                    "status": data.get("status"),
                    "robotClientUuid": data.get("robotClientUuid"),
                    "robotClientName": data.get("robotClientName"),
                    "machineName": data.get("machineName"),
                    "clientIp": data.get("clientIp"),
                    "windowsUserName": data.get("windowsUserName"),
                    "description": data.get("description"),
                    "ok": True,
                }
            )
        except Exception as exc:
            rows.append({"accountName": account, "ok": False, "error": str(exc)})
    return {"robots": rows, "total": len(rows)}

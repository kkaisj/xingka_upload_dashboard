from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...core.config import get_settings
from ...services.rpa_console import ConsoleService
from ...services.scheduler_retry_service import retry_failed_task

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class StopJobRequest(BaseModel):
    jobUuid: str


class RetryFailedTaskRequest(BaseModel):
    brand: str
    region: str
    action: str


@router.get("/status")
def scheduler_status(request: Request) -> dict[str, Any]:
    service = getattr(request.app.state, "scheduler_service", None)
    if service is None:
        return {
            "enabled": False,
            "active": False,
            "running": False,
            "completed": False,
            "thread_name": None,
            "last_error": "scheduler service not mounted",
        }
    return service.status_dict()


@router.post("/start")
def start_scheduler(request: Request) -> dict[str, Any]:
    service = getattr(request.app.state, "scheduler_service", None)
    if service is None:
        return {
            "ok": False,
            "started": False,
            "scheduler_status": {
                "enabled": False,
                "active": False,
                "running": False,
                "completed": False,
                "last_error": "scheduler service not mounted",
            },
        }
    started = service.start()
    return {"ok": True, "started": started, "scheduler_status": service.status_dict()}


@router.post("/stop-job")
def stop_job(req: StopJobRequest) -> dict[str, Any]:
    console = ConsoleService()
    resp = console.stop_job(req.jobUuid)
    return {"ok": True, "jobUuid": req.jobUuid, "response": resp}


@router.post("/retry-failed")
def retry_failed(req: RetryFailedTaskRequest, request: Request) -> dict[str, Any]:
    settings = get_settings()
    result = retry_failed_task(
        state_path=settings.state_file,
        brand=req.brand,
        region=req.region,
        action=req.action,
    )
    service = getattr(request.app.state, "scheduler_service", None)
    scheduler_status: dict[str, Any] | None = None
    restarted = False
    if service is not None and result["retried_count"] > 0:
        scheduler_status = service.status_dict()
        if scheduler_status.get("active"):
            restarted = bool(service.restart(timeout_seconds=10.0))
            scheduler_status = service.status_dict()
    return {
        "ok": True,
        "retried_count": result["retried_count"],
        "retried_work_ids": result["retried_work_ids"],
        "restarted": restarted,
        "scheduler_status": scheduler_status,
        "stage": {
            "index": result["state"].get("stage_index"),
            "name": result["state"].get("stage_name"),
        },
    }

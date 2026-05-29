import json
from pathlib import Path
from typing import Any

from .scheduler_engine import make_work_id, parse_work_id

VALID_ACTIONS = {"upload_oss", "hashkey", "upload_merged_file"}
STAGE_ORDER = ["upload_oss", "hashkey", "upload_merged_file"]


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if str(item).strip()]


def _matches_task(work_id: str, *, brand: str, region: str, action: str, default_brand: str) -> bool:
    parsed = parse_work_id(work_id, default_brand=default_brand)
    if not parsed:
        return False
    item_brand, item_region, item_action, _ = parsed
    return item_brand == brand and item_region == region and item_action == action


def _sync_stage_index(state: dict[str, Any], brand: str) -> None:
    regions = _normalize_list(state.get("parallel_regions"))
    accounts = _normalize_list(state.get("accounts"))
    done = set(_normalize_list(state.get("done")))
    failed = set(_normalize_list(state.get("failed")))

    for region in regions:
        for action in STAGE_ORDER:
            work_ids = [make_work_id(brand, region, action, account) for account in accounts]
            if any(work_id in failed for work_id in work_ids) or not all(work_id in done for work_id in work_ids):
                state["stage_index"] = regions.index(region) * len(STAGE_ORDER) + STAGE_ORDER.index(action)
                state["stage_name"] = action
                return

    state["stage_index"] = len(regions) * len(STAGE_ORDER)
    state["stage_name"] = "done"


def retry_failed_task(*, state_path: Path, brand: str, region: str, action: str) -> dict[str, Any]:
    clean_brand = str(brand or "").strip()
    clean_region = str(region or "").strip()
    clean_action = str(action or "").strip()
    if not clean_brand:
        raise ValueError("brand is required")
    if not clean_region:
        raise ValueError("region is required")
    if clean_action not in VALID_ACTIONS:
        raise ValueError("action is invalid")

    state = _load_state(state_path)
    default_brand = str(state.get("brand") or clean_brand)
    failed = _normalize_list(state.get("failed"))
    retried = [
        work_id
        for work_id in failed
        if _matches_task(work_id, brand=clean_brand, region=clean_region, action=clean_action, default_brand=default_brand)
    ]
    retried_set = set(retried)
    if not retried_set:
        return {"ok": True, "retried_count": 0, "retried_work_ids": [], "state": state}

    state["failed"] = [work_id for work_id in failed if work_id not in retried_set]
    attempts = state.get("attempts") if isinstance(state.get("attempts"), dict) else {}
    state["attempts"] = {str(work_id): value for work_id, value in attempts.items() if str(work_id) not in retried_set}
    state["inflight"] = [
        item
        for item in state.get("inflight", [])
        if not isinstance(item, dict) or str(item.get("work_id") or "") not in retried_set
    ]
    _sync_stage_index(state, clean_brand)
    _save_state(state_path, state)
    return {"ok": True, "retried_count": len(retried), "retried_work_ids": retried, "state": state}

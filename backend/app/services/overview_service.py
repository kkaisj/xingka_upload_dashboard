import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Task:
    brand: str
    region: str
    action: str

    @property
    def task_id(self) -> str:
        return f"{self.brand}|{self.region}:{self.action}"


def parse_list_env(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def parse_task_specs(raw: str, brand: str = "大众") -> list[Task]:
    items: list[Task] = []
    for token in parse_list_env(raw):
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            continue
        region = parts[0].strip()
        action = parts[1].strip()
        if not region or action not in {"upload_oss", "hashkey", "upload_merged_file"}:
            continue
        items.append(Task(brand=brand, region=region, action=action))
    return items


def build_task_plan(regions: list[str] | None = None, brand: str = "大众") -> list[Task]:
    all_regions = regions or ["ARGENTINA", "BRAZIL", "FAW-VW", "MEXICO", "SAIC VW", "SOUTH AFRICA", "USA"]
    tasks: list[Task] = []
    for r in all_regions:
        tasks.append(Task(brand=brand, region=r, action="upload_oss"))
        tasks.append(Task(brand=brand, region=r, action="hashkey"))
        tasks.append(Task(brand=brand, region=r, action="upload_merged_file"))
    return tasks


def make_work_id(brand: str, region: str, action: str, account: str) -> str:
    return f"{brand}|{region}:{action}:{account}"


def parse_work_id(work_id: str, default_brand: str = "大众") -> tuple[str, str, str, str] | None:
    if "|" in work_id:
        left, right = work_id.split("|", 1)
        parts = right.split(":", 2)
        if len(parts) != 3:
            return None
        return left or default_brand, parts[0], parts[1], parts[2]
    parts = work_id.split(":", 2)
    if len(parts) != 3:
        return None
    return default_brand, parts[0], parts[1], parts[2]


def filter_sequence_progress(
    work_ids: list[str],
    *,
    brand: str,
    regions: list[str],
    accounts: list[str],
    default_brand: str = "大众",
) -> list[str]:
    stage_order = ["upload_oss", "hashkey", "upload_merged_file"]
    valid_regions = set(regions)
    valid_accounts = set(accounts)
    current_brand_items: dict[tuple[str, str], set[str]] = {}
    passthrough: list[str] = []

    for work_id in work_ids:
        parsed = parse_work_id(str(work_id), default_brand=default_brand)
        if not parsed:
            continue
        item_brand, region, action, account = parsed
        if item_brand != brand:
            passthrough.append(str(work_id))
            continue
        if region not in valid_regions or action not in stage_order or account not in valid_accounts:
            continue
        current_brand_items.setdefault((region, action), set()).add(account)

    kept = list(passthrough)
    for region in regions:
        previous_complete = True
        for action in stage_order:
            accounts_for_action = current_brand_items.get((region, action), set())
            if previous_complete:
                kept.extend(make_work_id(brand, region, action, account) for account in accounts if account in accounts_for_action)
            if len(accounts_for_action) < len(accounts):
                previous_complete = False
    return kept


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"done": [], "failed": [], "inflight": []}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data.setdefault("done", [])
        data.setdefault("failed", [])
        data.setdefault("inflight", [])
        return data
    except Exception:
        return {"done": [], "failed": [], "inflight": []}


def load_events(event_path: Path, limit: int = 80) -> list[dict[str, Any]]:
    if not event_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in event_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    rows.reverse()
    seen_work_ids: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        work_id = str(row.get("work_id") or "").strip()
        if work_id:
            if work_id in seen_work_ids:
                continue
            seen_work_ids.add(work_id)
        filtered.append(row)
        if len(filtered) >= limit:
            break
    return filtered


def build_plan_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    inflight_list = state.get("inflight") or []
    default_brand = str(os.environ.get("BRAND", "") or state.get("brand", "") or "大众")
    done = set(str(w) for w in state.get("done", []) if str(w).strip())
    failed = set(str(w) for w in state.get("failed", []) if str(w).strip())
    accounts = state.get("accounts") or parse_list_env(os.environ.get("ACCOUNT_NAMES", ""))
    account_total = len(accounts)
    regions = parse_list_env(os.environ.get("PARALLEL_REGIONS", ""))
    if not regions:
        regions = state.get("parallel_regions") or ["ARGENTINA", "BRAZIL", "FAW-VW", "MEXICO", "SAIC VW", "SOUTH AFRICA", "USA"]
    done = set(
        filter_sequence_progress(
            list(done),
            brand=default_brand,
            regions=regions,
            accounts=accounts,
            default_brand=str(state.get("brand") or default_brand),
        )
    )
    failed = set(
        filter_sequence_progress(
            list(failed),
            brand=default_brand,
            regions=regions,
            accounts=accounts,
            default_brand=str(state.get("brand") or default_brand),
        )
    )

    running_by_task: dict[str, int] = {}
    running_task_ids = set()
    brands = {default_brand}
    for i in inflight_list:
        parsed = parse_work_id(str(i.get("work_id", "")), default_brand=default_brand)
        if not parsed:
            continue
        brand, region, action, _ = parsed
        tid = f"{brand}|{region}:{action}"
        running_task_ids.add(tid)
        running_by_task[tid] = running_by_task.get(tid, 0) + 1
        brands.add(brand)

    by_task: dict[str, dict[str, int]] = {}
    for wid in done:
        parsed = parse_work_id(wid, default_brand=default_brand)
        if not parsed:
            continue
        tid = f"{parsed[0]}|{parsed[1]}:{parsed[2]}"
        by_task.setdefault(tid, {"done": 0, "failed": 0})
        by_task[tid]["done"] += 1
    for wid in failed:
        parsed = parse_work_id(wid, default_brand=default_brand)
        if not parsed:
            continue
        tid = f"{parsed[0]}|{parsed[1]}:{parsed[2]}"
        by_task.setdefault(tid, {"done": 0, "failed": 0})
        by_task[tid]["failed"] += 1

    rows: list[dict[str, Any]] = []
    for brand in sorted(brands):
        for task in build_task_plan(regions=regions, brand=brand):
            tid = task.task_id
            done_count = by_task.get(tid, {}).get("done", 0)
            failed_count = by_task.get(tid, {}).get("failed", 0)
            running_count = running_by_task.get(tid, 0)
            started_count = done_count + failed_count + running_count
            pending_count = max(0, account_total - started_count)
            status = "pending"
            if failed_count > 0:
                status = "failed"
            elif done_count >= account_total and account_total > 0:
                status = "done"
            elif tid in running_task_ids:
                status = "running"
            rows.append(
                {
                    "task_id": tid,
                    "brand": brand,
                    "region": task.region,
                    "action": task.action,
                    "status": status,
                    "done_count": done_count,
                    "running_count": running_count,
                    "failed_count": failed_count,
                    "started_count": started_count,
                    "pending_count": pending_count,
                    "total": account_total,
                }
            )
    return rows


def build_overview(state_path: Path, event_path: Path, brand_filter: str | None = None) -> dict[str, Any]:
    state = load_state(state_path)
    all_plan_rows = build_plan_rows(state)
    all_events = load_events(event_path, limit=80)
    current_brand = str(os.environ.get("BRAND", "") or state.get("brand", ""))
    selected_brand = str(brand_filter or current_brand).strip()
    valid_actions = {"upload_oss", "hashkey", "upload_merged_file"}
    plan_rows = [r for r in all_plan_rows if not selected_brand or r.get("brand") == selected_brand]
    events = [
        e
        for e in all_events
        if (not selected_brand or e.get("brand") == selected_brand)
        and str(e.get("action", "")) in valid_actions
    ]

    work_total = sum(int(r.get("total", 0) or 0) for r in plan_rows)
    work_done = sum(int(r.get("done_count", 0) or 0) for r in plan_rows)
    work_running = sum(int(r.get("running_count", 0) or 0) for r in plan_rows)
    work_failed = sum(int(r.get("failed_count", 0) or 0) for r in plan_rows)
    work_pending = sum(int(r.get("pending_count", 0) or 0) for r in plan_rows)
    work_started = work_done + work_running + work_failed

    stage_name = str(state.get("stage_name", "") or "")
    progress = round((work_done / work_total) * 100, 2) if work_total else 0.0

    action_work_summary: dict[str, dict[str, Any]] = {}
    for action in ("upload_oss", "hashkey", "upload_merged_file"):
        action_rows = [r for r in plan_rows if str(r.get("action", "")) == action]
        total = sum(int(r.get("total", 0) or 0) for r in action_rows)
        done = sum(int(r.get("done_count", 0) or 0) for r in action_rows)
        running = sum(int(r.get("running_count", 0) or 0) for r in action_rows)
        failed = sum(int(r.get("failed_count", 0) or 0) for r in action_rows)
        pending = sum(int(r.get("pending_count", 0) or 0) for r in action_rows)
        action_work_summary[action] = {
            "total": total,
            "started": done + running + failed,
            "running": running,
            "done": done,
            "failed": failed,
            "pending": pending,
            "progress": round((done / total) * 100, 2) if total else 0.0,
        }

    return {
        "updated_at": int(time.time()),
        "brand": str(selected_brand or current_brand),
        "brands": [str(current_brand)],
        "stage": {"index": int(state.get("stage_index", 0) or 0), "name": stage_name},
        "summary": {
            "total": len(plan_rows),
            "done": len([r for r in plan_rows if r["status"] == "done"]),
            "running": len([r for r in plan_rows if r["status"] == "running"]),
            "pending": len([r for r in plan_rows if r["status"] == "pending"]),
            "failed": len([r for r in plan_rows if r["status"] == "failed"]),
        },
        "work_summary": {
            "total": work_total,
            "started": work_started,
            "running": work_running,
            "done": work_done,
            "failed": work_failed,
            "pending": work_pending,
            "progress": progress,
        },
        "stage_work_summary": {"total": 0, "started": 0, "running": 0, "done": 0, "failed": 0, "pending": 0, "progress": 0.0},
        "action_work_summary": action_work_summary,
        "inflight": state.get("inflight"),
        "plan": plan_rows,
        "events": events,
    }

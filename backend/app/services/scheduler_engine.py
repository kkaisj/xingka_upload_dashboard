import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .rpa_console import ConsoleService

logger = logging.getLogger(__name__)

JOB_STATUS_CREATED = "created"
JOB_STATUS_WAITING = "waiting"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_STOPPING = "stopping"
JOB_STATUS_FINISH = "finish"
JOB_STATUS_STOPPED = "stopped"
JOB_STATUS_ERROR = "error"
JOB_STATUS_SKIPPED = "skipped"
JOB_STATUS_CANCEL = "cancel"

TERMINAL_JOB_STATUSES = {
    JOB_STATUS_FINISH,
    JOB_STATUS_STOPPED,
    JOB_STATUS_ERROR,
    JOB_STATUS_SKIPPED,
    JOB_STATUS_CANCEL,
}


@dataclass(frozen=True)
class Task:
    brand: str
    region: str
    action: str

    @property
    def task_id(self) -> str:
        return f"{self.brand}|{self.region}:{self.action}"


@dataclass(frozen=True)
class WorkItem:
    brand: str
    region: str
    action: str
    account: str

    @property
    def work_id(self) -> str:
        return make_work_id(self.brand, self.region, self.action, self.account)


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        os.environ.setdefault(key.strip().lstrip("\ufeff"), value.strip())


def require_env(keys: List[str]) -> None:
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))


def parse_list_env(raw: str) -> List[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def parse_bool_env(raw: Optional[str], default: bool = False) -> bool:
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return default


def parse_task_specs(raw: str, brand: str = "大众") -> List[Task]:
    items: List[Task] = []
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


def normalize_job_status(raw_status: Any) -> str:
    if raw_status is None:
        return ""
    return str(raw_status).strip().lower()


def is_terminal_status(status: Any) -> bool:
    return normalize_job_status(status) in TERMINAL_JOB_STATUSES


def is_success_status(status: Any) -> bool:
    return normalize_job_status(status) == JOB_STATUS_FINISH


def is_failure_status(status: Any) -> bool:
    s = normalize_job_status(status)
    return s in (TERMINAL_JOB_STATUSES - {JOB_STATUS_FINISH})


def make_job_params(action: str, region: str, brand: str = "大众") -> List[Dict[str, Any]]:
    if action not in {"upload_oss", "hashkey", "upload_merged_file"}:
        raise ValueError(f"unknown action: {action}")
    return [
        {"name": "upload_oss", "value": action == "upload_oss", "type": "bool"},
        {"name": "hashkey", "value": action == "hashkey", "type": "bool"},
        {"name": "upload_merged_file", "value": action == "upload_merged_file", "type": "bool"},
        {"name": "brand", "value": brand, "type": "str"},
        {"name": "region", "value": region, "type": "str"},
    ]


def build_task_plan(regions: Optional[List[str]] = None, brand: str = "大众") -> List[Task]:
    all_regions = regions or ["ARGENTINA", "BRAZIL", "FAW-VW", "MEXICO", "SAIC VW", "SOUTH AFRICA", "USA"]
    tasks: List[Task] = []
    for r in all_regions:
        tasks.append(Task(brand=brand, region=r, action="upload_oss"))
        tasks.append(Task(brand=brand, region=r, action="hashkey"))
        tasks.append(Task(brand=brand, region=r, action="upload_merged_file"))
    return tasks


def extract_job_uuid(resp: Dict[str, Any]) -> Optional[str]:
    if not isinstance(resp, dict):
        return None
    if isinstance(resp.get("jobUuid"), str):
        return resp.get("jobUuid")
    data = resp.get("data")
    if isinstance(data, dict) and isinstance(data.get("jobUuid"), str):
        return data.get("jobUuid")
    return None


def make_work_id(brand: str, region: str, action: str, account: str) -> str:
    return f"{brand}|{region}:{action}:{account}"


def parse_work_id(work_id: str, default_brand: str = "大众") -> Optional[Tuple[str, str, str, str]]:
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
    work_ids: List[str],
    *,
    brand: str,
    regions: List[str],
    accounts: List[str],
    default_brand: str = "大众",
) -> List[str]:
    stage_order = ["upload_oss", "hashkey", "upload_merged_file"]
    valid_regions = set(regions)
    valid_accounts = set(accounts)
    current_brand_items: Dict[Tuple[str, str], set[str]] = {}
    passthrough: List[str] = []

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


class FeishuNotifier:
    def __init__(self, webhook_url: str, secret: str):
        self.webhook_url = webhook_url
        self.secret = secret

    TASK_CARD_TEMPLATES = {
        "任务启动": "blue",
        "任务完成": "green",
        "任务重试": "orange",
        "任务失败": "red",
    }

    def _make_sign(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), msg=b"", digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def send_text(self, text: str) -> None:
        timestamp = str(int(time.time()))
        payload = {
            "timestamp": timestamp,
            "sign": self._make_sign(timestamp),
            "msg_type": "text",
            "content": {"text": text},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        resp = requests.post(self.webhook_url, data=body, headers=headers, timeout=15)
        resp.raise_for_status()

    def send_task_card(self, title: str, fields: Dict[str, str]) -> None:
        timestamp = str(int(time.time()))
        content = "\n".join(f"**{name}**：{value}" for name, value in fields.items() if value)
        payload = {
            "timestamp": timestamp,
            "sign": self._make_sign(timestamp),
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": self.TASK_CARD_TEMPLATES.get(title, "blue"),
                    "title": {"tag": "plain_text", "content": title},
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content},
                    }
                ],
            },
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        resp = requests.post(self.webhook_url, data=body, headers=headers, timeout=15)
        resp.raise_for_status()


class Scheduler:
    def __init__(
        self,
        console: ConsoleService,
        notifier: FeishuNotifier,
        robot_uuid: str,
        accounts: List[str],
        parallel_regions: List[str],
        upload_regions: List[str],
        precompleted_tasks: Optional[List[Task]] = None,
        max_parallel_oss: Optional[int] = None,
        max_parallel_hashkey: Optional[int] = None,
        max_parallel_upload_merged_file: Optional[int] = None,
        poll_seconds: int = 20,
        max_retries: int = 2,
        state_path: str = ".task_state.json",
        event_path: str = ".task_events.jsonl",
        brand: str = "大众",
        strict_stage_order: bool = True,
    ):
        self.console = console
        self.notifier = notifier
        self.robot_uuid = robot_uuid
        self.accounts = accounts
        self.parallel_regions = parallel_regions
        self.upload_regions = upload_regions
        self.poll_seconds = poll_seconds
        self.max_retries = max_retries
        self.max_parallel_oss = max(1, int(max_parallel_oss or 10))
        self.max_parallel_hashkey = max(1, int(max_parallel_hashkey or len(accounts)))
        self.max_parallel_upload_merged_file = max(1, int(max_parallel_upload_merged_file or 10))
        self.state_path = Path(state_path)
        self.event_path = Path(event_path)
        self.brand = brand
        self.brands = [brand]
        self.precompleted_tasks = precompleted_tasks or []

        self.stages = self._build_stages()
        self.stage_index = 0
        self.done: List[str] = []
        self.failed: List[str] = []
        self.attempts: Dict[str, int] = {}
        self.inflight: List[Dict[str, Any]] = []

        self._load_state()
        self._apply_precompleted_tasks()
        self._sync_stage_index_with_progress()

    def _build_stages(self) -> List[Dict[str, Any]]:
        stages: List[Dict[str, Any]] = []
        for region in self.parallel_regions:
            stages.append({"name": "upload_oss", "regions": [region], "max_parallel": self.max_parallel_oss})
            stages.append({"name": "hashkey", "regions": [region], "max_parallel": self.max_parallel_hashkey})
            stages.append(
                {
                    "name": "upload_merged_file",
                    "regions": [region],
                    "max_parallel": self.max_parallel_upload_merged_file,
                }
            )
        return stages

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.stage_index = int(data.get("stage_index", 0))
        self.done = list(data.get("done", []))
        self.failed = list(data.get("failed", []))
        self.attempts = dict(data.get("attempts", {}))
        self.inflight = list(data.get("inflight", []))
        self.done = filter_sequence_progress(
            self.done,
            brand=self.brand,
            regions=self.parallel_regions,
            accounts=self.accounts,
            default_brand=str(data.get("brand") or self.brand),
        )
        self.failed = filter_sequence_progress(
            self.failed,
            brand=self.brand,
            regions=self.parallel_regions,
            accounts=self.accounts,
            default_brand=str(data.get("brand") or self.brand),
        )

    def _save_state(self) -> None:
        data = {
            "brand": self.brand,
            "stage_index": self.stage_index,
            "stage_name": self.stages[self.stage_index]["name"] if self.stage_index < len(self.stages) else "done",
            "parallel_regions": self.parallel_regions,
            "accounts": self.accounts,
            "done": self.done,
            "failed": self.failed,
            "attempts": self.attempts,
            "inflight": self.inflight,
        }
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _apply_precompleted_tasks(self) -> None:
        if not self.precompleted_tasks:
            return
        inflight_ids = {i.get("work_id") for i in self.inflight if isinstance(i, dict)}
        changed = False
        for task in self.precompleted_tasks:
            for account in self.accounts:
                wid = make_work_id(task.brand, task.region, task.action, account)
                if wid in inflight_ids or wid in self.failed or wid in self.done:
                    continue
                self.done.append(wid)
                changed = True
        if changed:
            self._save_state()

    def _append_event(self, event_type: str, item: WorkItem, extra: Dict[str, Any]) -> None:
        payload = {
            "ts": int(time.time()),
            "type": event_type,
            "work_id": item.work_id,
            "task_id": f"{item.brand}|{item.region}:{item.action}",
            "brand": item.brand,
            "region": item.region,
            "action": item.action,
            "account": item.account,
        }
        payload.update(extra)
        with self.event_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _notify(self, title: str, body: str) -> None:
        try:
            self.notifier.send_text(f"[{title}] {body}")
        except Exception:
            logger.exception("send feishu failed")

    def _notify_task(self, title: str, item: WorkItem, attempt: str = "", status: str = "", job_uuid: str = "") -> None:
        fields = {
            "品牌": item.brand,
            "地区": item.region,
            "上传阶段": item.action,
            "机器": item.account,
            "时间": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }
        if attempt:
            fields["尝试"] = attempt
        if status:
            fields["状态"] = status
        if job_uuid:
            fields["job"] = job_uuid
        try:
            self.notifier.send_task_card(title, fields)
        except AttributeError:
            self._notify(title, " | ".join(f"{name}={value}" for name, value in fields.items() if value))
        except Exception:
            logger.exception("send feishu failed")

    def _stage_items(self, stage_index: int) -> List[WorkItem]:
        if stage_index >= len(self.stages):
            return []
        stage = self.stages[stage_index]
        out: List[WorkItem] = []
        for region in stage["regions"]:
            for account in self.accounts:
                out.append(WorkItem(brand=self.brand, region=region, action=stage["name"], account=account))
        return out

    def _sync_stage_index_with_progress(self) -> None:
        for idx in range(len(self.stages)):
            items = self._stage_items(idx)
            if any(i.work_id in self.failed for i in items):
                self.stage_index = idx
                return
            if not all(i.work_id in self.done for i in items):
                self.stage_index = idx
                return
        self.stage_index = len(self.stages)

    def _advance_stage_if_ready(self) -> None:
        if self.stage_index >= len(self.stages):
            return
        items = self._stage_items(self.stage_index)
        if any(i.work_id in self.failed for i in items):
            return
        if all(i.work_id in self.done for i in items):
            self.stage_index += 1
            self._save_state()

    def _is_account_busy(self, account: str) -> bool:
        return any(i.get("account") == account for i in self.inflight)

    def _is_account_idle(self, account: str) -> bool:
        try:
            status_data = self.console.robot_status(account)
            status = normalize_job_status(status_data.get("status", ""))
            return status in {"idle", "connected"}
        except Exception:
            return False

    def _start_item(self, item: WorkItem) -> bool:
        if self._is_account_busy(item.account) or (not self._is_account_idle(item.account)):
            return False
        resp = self.console.start_job(item.account, self.robot_uuid, make_job_params(item.action, item.region, item.brand))
        job_uuid = extract_job_uuid(resp)
        if not job_uuid:
            raise RuntimeError(f"start_job missing jobUuid: {resp}")
        attempt = int(self.attempts.get(item.work_id, 0)) + 1
        self.attempts[item.work_id] = attempt
        self.inflight.append(
            {
                "brand": item.brand,
                "work_id": item.work_id,
                "task": {"brand": item.brand, "region": item.region, "action": item.action},
                "region": item.region,
                "action": item.action,
                "account": item.account,
                "job_uuid": job_uuid,
                "attempt": attempt,
                "started_at": int(time.time()),
            }
        )
        self._save_state()
        self._notify_task("任务启动", item, attempt=f"{attempt}/{self.max_retries + 1}", job_uuid=job_uuid)
        self._append_event("started", item, {"job_uuid": job_uuid, "attempt": attempt})
        return True

    def _poll_inflight(self) -> None:
        if not self.inflight:
            return
        remain: List[Dict[str, Any]] = []
        changed = False
        for running in self.inflight:
            parsed = parse_work_id(str(running.get("work_id", "")), self.brand)
            if not parsed:
                continue
            item = WorkItem(brand=parsed[0], region=parsed[1], action=parsed[2], account=parsed[3])
            try:
                detail = self.console.query_job_detail(running["job_uuid"])
            except Exception:
                remain.append(running)
                continue
            status = normalize_job_status(detail.get("status") or detail.get("sceneInstJobStatus"))
            if not status or not is_terminal_status(status):
                remain.append(running)
                continue
            changed = True
            if is_success_status(status):
                if item.work_id not in self.done:
                    self.done.append(item.work_id)
                self._notify_task("任务完成", item, status=status, job_uuid=running.get("job_uuid", ""))
                self._append_event("completed", item, {"status": status, "attempt": running.get("attempt", 1)})
                continue
            attempt = int(self.attempts.get(item.work_id, running.get("attempt", 1)))
            if attempt <= self.max_retries:
                self._notify_task("任务重试", item, status=status, attempt=f"{attempt}/{self.max_retries + 1}")
                self._append_event("retry", item, {"status": status, "attempt": attempt})
            else:
                if item.work_id not in self.failed:
                    self.failed.append(item.work_id)
                self._notify_task("任务失败", item, status=status, attempt=f"{attempt}/{self.max_retries + 1}")
                self._append_event("failed", item, {"status": status, "attempt": attempt})
        self.inflight = remain
        if changed:
            self._save_state()

    def _start_stage_work(self) -> None:
        if self.stage_index >= len(self.stages):
            return
        stage = self.stages[self.stage_index]
        items = self._stage_items(self.stage_index)
        if any(i.work_id in self.failed for i in items):
            return
        inflight_current_stage = [i for i in self.inflight if i.get("action") == stage["name"] and i.get("region") in stage["regions"]]
        slots = max(0, int(stage.get("max_parallel", 1)) - len(inflight_current_stage))
        if slots <= 0:
            return
        started = 0
        for item in items:
            if started >= slots:
                break
            if item.work_id in self.done or item.work_id in self.failed:
                continue
            if any(i.get("work_id") == item.work_id for i in self.inflight):
                continue
            try:
                if self._start_item(item):
                    started += 1
            except Exception:
                logger.exception("start item failed: %s", item.work_id)

    def run_forever(self, stop_event: Optional[Any] = None) -> None:
        logger.info("scheduler started.")
        self._save_state()
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                self._poll_inflight()
                self._advance_stage_if_ready()
                self._start_stage_work()
            except Exception:
                logger.exception("scheduler loop error")
            if stop_event is not None:
                if stop_event.wait(self.poll_seconds):
                    break
            else:
                time.sleep(self.poll_seconds)
        logger.info("scheduler stopped.")

    def is_complete(self) -> bool:
        return self.stage_index >= len(self.stages)


def parse_accounts(raw: str) -> List[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def create_scheduler_from_env() -> Scheduler:
    require_env([
        "CONSOLE_ACCESS_KEY_ID",
        "CONSOLE_ACCESS_SECRET",
        "CONSOLE_HOST",
        "FEISHU_WEBHOOK_URL",
        "FEISHU_SECRET",
        "ROBOT_UUID",
        "ACCOUNT_NAMES",
    ])

    webhook = os.environ["FEISHU_WEBHOOK_URL"]
    secret = os.environ["FEISHU_SECRET"]
    robot_uuid = os.environ["ROBOT_UUID"]
    account_names = parse_accounts(os.environ["ACCOUNT_NAMES"])
    poll_seconds = int(os.environ.get("POLL_SECONDS", "20"))
    max_retries = int(os.environ.get("MAX_RETRIES", "2"))
    max_parallel_oss = int(os.environ.get("MAX_PARALLEL_OSS", "10"))
    max_parallel_hashkey = int(os.environ.get("MAX_PARALLEL_HASHKEY", "90"))
    max_parallel_upload_merged_file = int(os.environ.get("MAX_PARALLEL_UPLOAD_MERGED_FILE", "10"))
    state_path = os.environ.get("TASK_STATE_FILE", ".task_state.json")
    event_path = os.environ.get("TASK_EVENT_FILE", ".task_events.jsonl")
    brand = os.environ.get("BRAND", "奥迪")
    regions = parse_list_env(os.environ.get("PARALLEL_REGIONS", "ARGENTINA,BRAZIL,FAW-VW,MEXICO,SAIC VW,SOUTH AFRICA,USA"))
    precompleted_tasks = parse_task_specs(os.environ.get("PRECOMPLETED_TASKS", ""), brand=brand)

    notifier = FeishuNotifier(webhook, secret)
    console = ConsoleService()
    return Scheduler(
        console=console,
        notifier=notifier,
        robot_uuid=robot_uuid,
        accounts=account_names,
        parallel_regions=regions,
        upload_regions=regions,
        precompleted_tasks=precompleted_tasks,
        max_parallel_oss=max_parallel_oss,
        max_parallel_hashkey=max_parallel_hashkey,
        max_parallel_upload_merged_file=max_parallel_upload_merged_file,
        poll_seconds=poll_seconds,
        max_retries=max_retries,
        state_path=state_path,
        event_path=event_path,
        brand=brand,
        strict_stage_order=True,
    )


def main() -> None:
    load_dotenv(str(Path(__file__).resolve().parents[2] / ".env"))
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    scheduler = create_scheduler_from_env()
    scheduler.run_forever()


if __name__ == "__main__":
    main()

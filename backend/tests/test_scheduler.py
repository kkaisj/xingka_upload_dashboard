from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.services.scheduler_engine import (
    FeishuNotifier,
    Scheduler,
    Task,
    WorkItem,
    build_task_plan,
    extract_job_uuid,
    filter_sequence_progress,
    is_failure_status,
    is_success_status,
    is_terminal_status,
    make_job_params,
    parse_task_specs,
)


class SchedulerTests(unittest.TestCase):
    def test_scheduler_start_item_uses_item_brand_param(self):
        class DummyConsole:
            def __init__(self):
                self.last_params = None

            def robot_status(self, account):
                return {"status": "idle"}

            def start_job(self, account, app_uuid, job_params):
                self.last_params = job_params
                return {"data": {"jobUuid": "job-1"}}

            def query_job_detail(self, job_uuid):
                return {"status": "running"}

        class DummyNotifier(FeishuNotifier):
            def __init__(self):
                pass

            def send_text(self, text: str) -> None:
                return

        with TemporaryDirectory() as d:
            console = DummyConsole()
            scheduler = Scheduler(
                console=console,
                notifier=DummyNotifier(),
                robot_uuid="robot-uuid",
                accounts=["xk001-1@ydsjljq"],
                parallel_regions=["USA"],
                upload_regions=["USA"],
                poll_seconds=1,
                max_retries=1,
                state_path=str(Path(d) / "state.json"),
                event_path=str(Path(d) / "events.jsonl"),
                brand="默认品牌",
                strict_stage_order=True,
            )
            scheduler._is_account_idle = lambda account: True  # type: ignore[method-assign]

            ok = scheduler._start_item(WorkItem(brand="奥迪", region="USA", action="upload_oss", account="xk001-1@ydsjljq"))
            self.assertTrue(ok)
            params = {p["name"]: p["value"] for p in (console.last_params or [])}
            self.assertEqual(params.get("brand"), "奥迪")
            self.assertTrue(params.get("upload_oss"))

    def test_make_job_params_only_one_true(self):
        params = make_job_params("upload_oss", "MEXICO")
        by_name = {item["name"]: item["value"] for item in params}
        self.assertTrue(by_name["upload_oss"])
        self.assertFalse(by_name["hashkey"])
        self.assertFalse(by_name["upload_merged_file"])

    def test_make_job_params_hashkey_only(self):
        params = make_job_params("hashkey", "FAW-VW")
        by_name = {item["name"]: item["value"] for item in params}
        self.assertFalse(by_name["upload_oss"])
        self.assertTrue(by_name["hashkey"])
        self.assertFalse(by_name["upload_merged_file"])
        self.assertEqual(by_name["region"], "FAW-VW")

    def test_build_task_plan_order(self):
        plan = build_task_plan(regions=["ARGENTINA", "BRAZIL"])
        self.assertEqual(plan[0], Task(brand="大众", region="ARGENTINA", action="upload_oss"))
        self.assertEqual(plan[1], Task(brand="大众", region="ARGENTINA", action="hashkey"))
        self.assertEqual(plan[2], Task(brand="大众", region="ARGENTINA", action="upload_merged_file"))
        self.assertEqual(plan[3], Task(brand="大众", region="BRAZIL", action="upload_oss"))

    def test_extract_job_uuid(self):
        self.assertEqual(extract_job_uuid({"jobUuid": "abc"}), "abc")
        self.assertEqual(extract_job_uuid({"data": {"jobUuid": "xyz"}}), "xyz")
        self.assertIsNone(extract_job_uuid({"data": {}}))

    def test_job_status_terminal_rules(self):
        self.assertFalse(is_terminal_status("created"))
        self.assertFalse(is_terminal_status("waiting"))
        self.assertFalse(is_terminal_status("running"))
        self.assertFalse(is_terminal_status("stopping"))
        self.assertTrue(is_terminal_status("finish"))
        self.assertTrue(is_terminal_status("stopped"))
        self.assertTrue(is_terminal_status("error"))
        self.assertTrue(is_terminal_status("skipped"))
        self.assertTrue(is_terminal_status("cancel"))

    def test_job_status_success_failure(self):
        self.assertTrue(is_success_status("finish"))
        self.assertFalse(is_success_status("error"))
        self.assertTrue(is_failure_status("error"))
        self.assertTrue(is_failure_status("stopped"))
        self.assertTrue(is_failure_status("cancel"))
        self.assertFalse(is_failure_status("running"))

    def test_parse_task_specs(self):
        specs = parse_task_specs("USA:upload_oss,USA:hashkey,SOUTH AFRICA:upload_merged_file,badtoken")
        self.assertEqual(
            specs,
            [
                Task(brand="大众", region="USA", action="upload_oss"),
                Task(brand="大众", region="USA", action="hashkey"),
                Task(brand="大众", region="SOUTH AFRICA", action="upload_merged_file"),
            ],
        )

    def test_filter_sequence_progress_keeps_hashkey_after_upload_oss_complete(self):
        accounts = ["xk001@ydsjljq", "xk001-2@ydsjljq"]
        rows = [
            "奥迪|USA:upload_oss:xk001@ydsjljq",
            "奥迪|USA:upload_oss:xk001-2@ydsjljq",
            "奥迪|USA:hashkey:xk001@ydsjljq",
        ]
        filtered = filter_sequence_progress(rows, brand="奥迪", regions=["USA"], accounts=accounts)
        self.assertEqual(
            filtered,
            [
                "奥迪|USA:upload_oss:xk001@ydsjljq",
                "奥迪|USA:upload_oss:xk001-2@ydsjljq",
                "奥迪|USA:hashkey:xk001@ydsjljq",
            ],
        )

    def test_run_forever_keeps_running_after_starting_one_batch(self):
        import threading
        import time

        class DummyConsole:
            def robot_status(self, account):
                return {"status": "idle"}

            def start_job(self, account, app_uuid, job_params):
                return {"data": {"jobUuid": f"job-{account}"}}

            def query_job_detail(self, job_uuid):
                return {"status": "running"}

        class DummyNotifier(FeishuNotifier):
            def __init__(self):
                pass

            def send_text(self, text: str) -> None:
                return

        with TemporaryDirectory() as d:
            stop_event = threading.Event()
            scheduler = Scheduler(
                console=DummyConsole(),
                notifier=DummyNotifier(),
                robot_uuid="robot-uuid",
                accounts=["xk001@ydsjljq", "xk001-2@ydsjljq", "xk001-3@ydsjljq"],
                parallel_regions=["ARGENTINA"],
                upload_regions=["ARGENTINA"],
                max_parallel_oss=2,
                poll_seconds=1,
                state_path=str(Path(d) / "state.json"),
                event_path=str(Path(d) / "events.jsonl"),
                brand="奥迪",
            )
            thread = threading.Thread(target=scheduler.run_forever, kwargs={"stop_event": stop_event}, daemon=True)
            thread.start()
            time.sleep(0.2)
            self.assertTrue(thread.is_alive())
            self.assertEqual(len(scheduler.inflight), 2)
            stop_event.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_feishu_task_notification_uses_interactive_card_style(self):
        import backend.app.services.scheduler_engine as scheduler_engine

        captured = {}

        class DummyResponse:
            def raise_for_status(self):
                return None

        def fake_post(url, data, headers, timeout):
            captured["payload"] = json.loads(data.decode("utf-8"))
            captured["headers"] = headers
            return DummyResponse()

        old_post = scheduler_engine.requests.post
        scheduler_engine.requests.post = fake_post
        try:
            notifier = FeishuNotifier("https://example.test/webhook", "secret")
            notifier.send_task_card(
                "任务完成",
                {
                    "品牌": "奥迪",
                    "地区": "BRAZIL",
                    "上传阶段": "upload_oss",
                    "机器": "xk001-11@ydsjljq",
                    "状态": "finish",
                },
            )
        finally:
            scheduler_engine.requests.post = old_post

        payload = captured["payload"]
        self.assertEqual(payload["msg_type"], "interactive")
        self.assertEqual(payload["card"]["header"]["template"], "green")
        self.assertEqual(payload["card"]["header"]["title"]["content"], "任务完成")
        content = payload["card"]["elements"][0]["text"]["content"]
        self.assertIn("**品牌**：奥迪", content)
        self.assertIn("**地区**：BRAZIL", content)
        self.assertEqual(captured["headers"]["Content-Type"], "application/json; charset=utf-8")


if __name__ == "__main__":
    unittest.main()



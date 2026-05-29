from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.services.overview_service import build_plan_rows, filter_sequence_progress, load_events, load_state


class MonitorDataTests(unittest.TestCase):
    def test_load_state_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            data = load_state(Path(d) / "none.json")
            self.assertEqual(data["done"], [])
            self.assertEqual(data["inflight"], [])

    def test_load_events_keep_latest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "events.jsonl"
            rows = [
                {"type": "start", "i": 1},
                {"type": "success", "i": 2},
                {"type": "fail", "i": 3},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            events = load_events(p, limit=2)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["i"], 3)
            self.assertEqual(events[1]["i"], 2)

    def test_build_plan_rows_status(self):
        state = {
            "brand": "大众",
            "accounts": ["xk001@ydsjljq"],
            "parallel_regions": ["MEXICO", "FAW-VW"],
            "upload_regions": ["MEXICO", "FAW-VW"],
            "done": ["大众|MEXICO:upload_oss:xk001@ydsjljq"],
            "failed": ["大众|FAW-VW:upload_oss:xk001@ydsjljq"],
            "inflight": [
                {
                    "work_id": "大众|MEXICO:hashkey:xk001@ydsjljq",
                    "region": "MEXICO",
                    "action": "hashkey",
                    "account": "xk001@ydsjljq",
                }
            ],
        }
        rows = build_plan_rows(state)
        by_id = {r["task_id"]: r["status"] for r in rows}
        self.assertEqual(by_id["大众|MEXICO:upload_oss"], "done")
        self.assertEqual(by_id["大众|MEXICO:hashkey"], "running")
        self.assertEqual(by_id["大众|FAW-VW:upload_oss"], "failed")

    def test_filter_sequence_progress_removes_future_stage_when_previous_incomplete(self):
        accounts = ["xk001@ydsjljq", "xk001-2@ydsjljq"]
        rows = [
            "奥迪|USA:hashkey:xk001@ydsjljq",
            "奥迪|USA:hashkey:xk001-2@ydsjljq",
            "奥迪|ARGENTINA:upload_oss:xk001@ydsjljq",
        ]
        filtered = filter_sequence_progress(rows, brand="奥迪", regions=["ARGENTINA", "USA"], accounts=accounts)
        self.assertEqual(filtered, ["奥迪|ARGENTINA:upload_oss:xk001@ydsjljq"])


if __name__ == "__main__":
    unittest.main()



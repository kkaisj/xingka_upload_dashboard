from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import unittest
from tempfile import TemporaryDirectory

from backend.app.services.scheduler_retry_service import retry_failed_task


class SchedulerRetryServiceTests(unittest.TestCase):
    def test_retry_failed_task_clears_only_matching_failed_items(self):
        with TemporaryDirectory() as d:
            state_path = Path(d) / "state.json"
            failed_target = "奥迪|SAIC VW:upload_merged_file:xk001@ydsjljq"
            failed_other_stage = "奥迪|BRAZIL:hashkey:xk002@ydsjljq"
            failed_other_brand = "大众|SAIC VW:upload_merged_file:xk003@ydsjljq"
            state_path.write_text(
                json.dumps(
                    {
                        "brand": "奥迪",
                        "stage_index": 2,
                        "stage_name": "upload_merged_file",
                        "parallel_regions": ["SAIC VW", "BRAZIL"],
                        "accounts": ["xk001@ydsjljq", "xk002@ydsjljq", "xk003@ydsjljq"],
                        "done": [
                            "奥迪|SAIC VW:upload_oss:xk001@ydsjljq",
                            "奥迪|SAIC VW:upload_oss:xk002@ydsjljq",
                            "奥迪|SAIC VW:upload_oss:xk003@ydsjljq",
                            "奥迪|SAIC VW:hashkey:xk001@ydsjljq",
                            "奥迪|SAIC VW:hashkey:xk002@ydsjljq",
                            "奥迪|SAIC VW:hashkey:xk003@ydsjljq",
                        ],
                        "failed": [failed_target, failed_other_stage, failed_other_brand],
                        "attempts": {
                            failed_target: 3,
                            failed_other_stage: 2,
                            failed_other_brand: 4,
                        },
                        "inflight": [{"work_id": failed_target, "job_uuid": "old-job"}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = retry_failed_task(
                state_path=state_path,
                brand="奥迪",
                region="SAIC VW",
                action="upload_merged_file",
            )

            self.assertEqual(result["retried_count"], 1)
            self.assertEqual(result["retried_work_ids"], [failed_target])
            data = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn(failed_target, data["failed"])
            self.assertIn(failed_other_stage, data["failed"])
            self.assertIn(failed_other_brand, data["failed"])
            self.assertNotIn(failed_target, data["attempts"])
            self.assertIn(failed_other_stage, data["attempts"])
            self.assertIn(failed_other_brand, data["attempts"])
            self.assertEqual(data["inflight"], [])
            self.assertEqual(data["stage_name"], "upload_merged_file")


if __name__ == "__main__":
    unittest.main()

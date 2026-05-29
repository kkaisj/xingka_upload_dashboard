from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import unittest
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from backend.app.api.v1 import scheduler as scheduler_api


class SchedulerApiTests(unittest.TestCase):
    def test_retry_failed_restarts_active_scheduler(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            state_path = root / "state.json"
            failed = "奥迪|SAIC VW:hashkey:xk001@ydsjljq"
            state_path.write_text(
                json.dumps(
                    {
                        "brand": "奥迪",
                        "stage_index": 1,
                        "stage_name": "hashkey",
                        "parallel_regions": ["SAIC VW"],
                        "accounts": ["xk001@ydsjljq"],
                        "done": ["奥迪|SAIC VW:upload_oss:xk001@ydsjljq"],
                        "failed": [failed],
                        "attempts": {failed: 3},
                        "inflight": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            class DummySettings:
                state_file = state_path

            scheduler_service = Mock()
            scheduler_service.status_dict.return_value = {"active": True, "running": True}
            scheduler_service.restart.return_value = True
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(scheduler_service=scheduler_service)))

            with patch("backend.app.api.v1.scheduler.get_settings", return_value=DummySettings()):
                resp = scheduler_api.retry_failed(
                    scheduler_api.RetryFailedTaskRequest(brand="奥迪", region="SAIC VW", action="hashkey"),
                    request,
                )

            self.assertEqual(resp["retried_count"], 1)
            scheduler_service.restart.assert_called_once()


if __name__ == "__main__":
    unittest.main()

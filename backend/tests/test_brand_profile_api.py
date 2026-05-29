from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.app.api.v1 import config as config_api


class BrandProfileApiTests(unittest.TestCase):
    def test_brand_profile_api_roundtrip_and_apply(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "backend").mkdir()
            (root / "backend" / ".env").write_text(
                "BRAND=奥迪\nPARALLEL_REGIONS=USA\nREGION_CATALOG=USA\n",
                encoding="utf-8",
            )
            (root / ".task_state.json").write_text(
                json.dumps(
                    {
                        "brand": "奥迪",
                        "stage_index": 2,
                        "stage_name": "hashkey",
                        "parallel_regions": ["USA"],
                        "accounts": ["xk001@ydsjljq"],
                        "done": ["大众|USA:upload_oss:xk001@ydsjljq"],
                        "failed": [],
                        "attempts": {},
                        "inflight": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            class DummySettings:
                root_dir = root
                state_file = root / ".task_state.json"

            with patch.dict(os.environ, {}, clear=True), patch("backend.app.api.v1.config.get_settings", return_value=DummySettings()):
                saved = config_api.put_brand_profiles(
                    config_api.SaveBrandProfilesRequest(
                        profiles={"大众": {"regions": ["ARGENTINA", "BRAZIL"]}}
                    )
                )
                self.assertEqual(saved["profiles"]["大众"]["regions"], ["ARGENTINA", "BRAZIL"])

                loaded = config_api.get_brand_profiles()
                self.assertEqual(loaded["profiles"]["大众"]["regions"], ["ARGENTINA", "BRAZIL"])

                applied = config_api.post_apply_brand_profile(
                    config_api.ApplyBrandProfileRequest(brand="大众", reset_progress=True)
                )
                self.assertEqual(applied["brand"], "大众")
                self.assertEqual(applied["config"]["BRAND"], "大众")

                state = json.loads((root / ".task_state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["brand"], "大众")
                self.assertEqual(state["stage_index"], 0)
                self.assertEqual(state["done"], [])


if __name__ == "__main__":
    unittest.main()

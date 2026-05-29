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

from backend.app.services.brand_profile_service import (
    apply_brand_profile,
    load_brand_profiles,
    save_brand_profiles,
)


class BrandProfileTests(unittest.TestCase):
    def test_load_profiles_reads_json_file(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "backend").mkdir()
            (root / "backend" / "brand_profiles.json").write_text(
                json.dumps(
                    {
                        "奥迪": {"regions": ["USA", "BRAZIL"]},
                        "大众": {"regions": ["ARGENTINA"]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            profiles = load_brand_profiles(root)

            self.assertEqual(profiles["奥迪"]["regions"], ["USA", "BRAZIL"])
            self.assertEqual(profiles["大众"]["regions"], ["ARGENTINA"])

    def test_save_profiles_deduplicates_blank_regions(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "backend").mkdir()

            profiles = save_brand_profiles(
                root,
                {
                    "大众": {"regions": ["USA", "USA", "", " BRAZIL "]},
                    "": {"regions": ["IGNORED"]},
                },
            )

            self.assertEqual(profiles, {"大众": {"regions": ["USA", "BRAZIL"]}})
            saved = json.loads((root / "backend" / "brand_profiles.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, profiles)

    def test_apply_profile_updates_env_and_resets_current_brand_progress(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            backend = root / "backend"
            backend.mkdir()
            (backend / ".env").write_text(
                "\n".join(
                    [
                        "BRAND=奥迪",
                        "PARALLEL_REGIONS=USA",
                        "REGION_CATALOG=USA",
                        "ACCOUNT_NAMES=xk001@ydsjljq",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (backend / "brand_profiles.json").write_text(
                json.dumps({"大众": {"regions": ["ARGENTINA", "BRAZIL"]}}, ensure_ascii=False),
                encoding="utf-8",
            )
            state_path = root / ".task_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "brand": "奥迪",
                        "stage_index": 4,
                        "stage_name": "hashkey",
                        "parallel_regions": ["USA"],
                        "accounts": ["xk001@ydsjljq"],
                        "done": [
                            "奥迪|USA:upload_oss:xk001@ydsjljq",
                            "大众|USA:upload_oss:xk001@ydsjljq",
                        ],
                        "failed": ["大众|USA:hashkey:xk001@ydsjljq"],
                        "attempts": {},
                        "inflight": [
                            {
                                "brand": "大众",
                                "work_id": "大众|USA:upload_merged_file:xk001@ydsjljq",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                result = apply_brand_profile(root, "大众", reset_progress=True, state_path=state_path)

            self.assertEqual(result["config"]["BRAND"], "大众")
            self.assertEqual(result["config"]["PARALLEL_REGIONS"], "ARGENTINA,BRAZIL")
            self.assertEqual(result["config"]["REGION_CATALOG"], "ARGENTINA,BRAZIL")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["brand"], "大众")
            self.assertEqual(state["stage_index"], 0)
            self.assertEqual(state["stage_name"], "upload_oss")
            self.assertEqual(state["parallel_regions"], ["ARGENTINA", "BRAZIL"])
            self.assertEqual(state["done"], ["奥迪|USA:upload_oss:xk001@ydsjljq"])
            self.assertEqual(state["failed"], [])
            self.assertEqual(state["inflight"], [])


if __name__ == "__main__":
    unittest.main()

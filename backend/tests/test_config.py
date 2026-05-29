from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import unittest

from backend.app.core.config import parse_env_int


class ConfigTests(unittest.TestCase):
    def test_parse_env_int_with_empty_string_fallback_default(self):
        self.assertEqual(parse_env_int("", 8000), 8000)

    def test_parse_env_int_with_invalid_string_fallback_default(self):
        self.assertEqual(parse_env_int("abc", 20), 20)

    def test_parse_env_int_with_valid_number(self):
        self.assertEqual(parse_env_int("9000", 8000), 9000)


if __name__ == "__main__":
    unittest.main()



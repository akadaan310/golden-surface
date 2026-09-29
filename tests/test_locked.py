"""The locked tabs survive every close path on the twin side (stdlib only).

  python3 -m unittest tests.test_locked
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))
from twin import TwinModel, is_locked  # noqa: E402


def tabs():
    return [{"id": "lock-luna", "owner": "r", "url": "https://l/"},
            {"id": "lock-acsp", "owner": "n", "url": "https://a/"},
            {"id": "lock-trial", "owner": "abed", "url": "https://t/"},
            {"id": "t1", "owner": "r", "url": "https://x/"}]


class LockedTabs(unittest.TestCase):
    def test_marker(self):
        self.assertTrue(is_locked("lock-luna"))
        self.assertFalse(is_locked("t1"))
        self.assertFalse(is_locked(None))

    def test_closetab_skips_locked(self):
        tw = TwinModel(tabs=tabs(), active="lock-luna")
        tw.new_op("closetab", {"tab": "lock-luna"})
        self.assertIn("lock-luna", [t["id"] for t in tw.model["tabs"]])
        tw.new_op("closetab", {"tab": "t1"})
        self.assertNotIn("t1", [t["id"] for t in tw.model["tabs"]])

    def test_telemetry_marks_locked(self):
        tw = TwinModel(tabs=tabs(), active="t1")
        tel = {t["id"]: t for t in tw.telemetry(extended=True)["tabs"]}
        self.assertTrue(tel["lock-trial"]["locked"])
        self.assertFalse(tel["t1"]["locked"])
        # /state keeps the spec's shape
        self.assertEqual(set(tw.telemetry()["tabs"][0]), {"id", "owner", "url", "title", "signedIn"})


if __name__ == "__main__":
    unittest.main()

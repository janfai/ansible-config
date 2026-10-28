import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class GuardianVendor(unittest.TestCase):
    def test_vendored_runtime_contains_fixes(self):
        text = (BASE / "roles/guardian/files/guardian").read_text()
        for marker in ("next_cycle_delay", "station_identity", "busy"):
            self.assertIn(marker, text, marker)


if __name__ == "__main__":
    unittest.main()

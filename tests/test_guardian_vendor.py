import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class GuardianVendor(unittest.TestCase):
    def test_vendored_runtime_contains_fixes(self):
        text = (BASE / "roles/guardian/files/guardian").read_text()
        for marker in ("next_cycle_delay", "station_identity", "busy"):
            self.assertIn(marker, text, marker)
        self.assertIn('configured_provider == "none"', text)

    def test_none_provider_is_default_and_skips_agent_setup(self):
        defaults = (BASE / "roles/guardian/defaults/main.yml").read_text()
        tasks = (BASE / "roles/guardian/tasks/main.yml").read_text()
        self.assertIn("guardian_provider: none", defaults)
        self.assertIn("guardian_provider in ['none', 'codex', 'claude']", tasks)
        self.assertIn("guardian_enabled | bool and guardian_provider != 'none'", tasks)
        self.assertIn("agent_provider: \"{{ guardian_provider }}\"", tasks)
        self.assertIn("guardian_provider == 'none'", tasks)


if __name__ == "__main__":
    unittest.main()

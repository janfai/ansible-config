import unittest
from pathlib import Path
import re

import yaml
from jinja2 import Environment

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

    def test_allowed_signers_template_renders_two_valid_lines(self):
        tasks = yaml.safe_load((BASE / "roles/guardian/tasks/main.yml").read_text())
        task = next(item for item in tasks if item.get("name") == "Zapsat veřejný klíč mastera pro ověřování podpisů")
        environment = Environment()
        environment.filters["regex_search"] = lambda value, pattern: re.search(pattern, value).group(0)
        template = environment.from_string(task["ansible.builtin.copy"]["content"])
        rendered = template.render(guardian_allowed_signers="jan ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        lines = rendered.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].split()[0], "jan")
        self.assertEqual(lines[0].split()[1], "ssh-ed25519")
        self.assertEqual(lines[1].split()[0], "router")
        self.assertEqual(lines[1].split()[1], 'namespaces="guardian-board"')


if __name__ == "__main__":
    unittest.main()

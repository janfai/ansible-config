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
        self.assertNotIn("UPGRADE_GUARDIAN", text)

    def test_none_provider_is_default_and_skips_agent_setup(self):
        defaults = (BASE / "roles/guardian/defaults/main.yml").read_text()
        tasks = (BASE / "roles/guardian/tasks/main.yml").read_text()
        self.assertIn("guardian_provider: none", defaults)
        self.assertIn("guardian_provider in ['none', 'codex', 'claude']", tasks)
        self.assertIn("guardian_enabled | bool and guardian_provider != 'none'", tasks)
        self.assertIn("agent_provider: \"{{ guardian_provider }}\"", tasks)
        self.assertIn("guardian_provider == 'none'", tasks)
        self.assertIn("guardian_mode: temporary", defaults)
        self.assertIn('mode: "{{ guardian_mode }}"', tasks)
        self.assertIn("guardian.service", tasks)

    def test_existing_station_paths_move_before_canonical_paths_are_created(self):
        tasks = yaml.safe_load((BASE / "roles/guardian/tasks/main.yml").read_text())
        migration = next(i for i, task in enumerate(tasks) if task.get("name") == "Přesunout staré adresáře Guardiana bez slučování kolizních dat")
        create = next(i for i, task in enumerate(tasks) if task.get("name") == "Vytvořit adresáře Guardiana")
        self.assertLess(migration, create)
        self.assertIn("mv --", tasks[migration]["ansible.builtin.shell"])
        self.assertIn("exit 42", tasks[migration]["ansible.builtin.shell"])
        retire = next(task for task in tasks if task.get("name") == "Odstranit soubory a profily Guardiana")
        self.assertEqual(set(retire["loop"]), {"/opt/guardian", "/etc/guardian", "/var/lib/guardian", "/opt/upgrade-guardian", "/etc/upgrade-guardian", "/var/lib/upgrade-guardian"})

    def test_canonical_unit_and_vendor_manifest_match(self):
        files = BASE / "roles/guardian/files"
        self.assertTrue((files / "guardian.service").is_file())
        self.assertEqual({path.name for path in files.glob("*.service")}, {"guardian.service"})
        result = __import__("subprocess").run(["sha256sum", "--check", "MANIFEST"], cwd=files, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

import unittest
from pathlib import Path
import re

import yaml
from jinja2 import Environment

BASE = Path(__file__).resolve().parents[1]


class GuardianVendor(unittest.TestCase):
    def test_vm_linux_guardian_config_and_age_gate_precede_sops(self):
        host = yaml.safe_load((BASE / "host_vars/vm-linux.yml").read_text())
        playbook = yaml.safe_load((BASE / "local.yml").read_text())[0]
        tasks = playbook["pre_tasks"]
        guardian_role = next(role for role in playbook["roles"] if isinstance(role, dict) and role.get("role") == "guardian")
        age_check = next(i for i, task in enumerate(tasks) if task.get("name") == "Vyžadovat root-only age identitu před SOPS lookupem")
        station_sops = next(i for i, task in enumerate(tasks) if task.get("name") == "Načíst šifrovaná tajemství stanice")
        self.assertLess(age_check, station_sops)
        self.assertEqual(host["guardian_provider"], "codex")
        self.assertTrue(host["guardian_enabled"])
        self.assertEqual(host["guardian_mode"], "permanent")
        self.assertTrue(host["guardian_camouflage"])
        self.assertTrue(host["guardian_git_enabled"])
        self.assertEqual(guardian_role["guardian_mode"], "{{ station_config.guardian_mode | default('temporary') }}")
        self.assertEqual(guardian_role["guardian_camouflage"], "{{ station_config.guardian_camouflage | default(false) }}")

    def test_regular_station_keeps_default_guardian_profile_and_vm_linux_is_explicit_exception(self):
        defaults = yaml.safe_load((BASE / "roles/guardian/defaults/main.yml").read_text())
        regular = yaml.safe_load((BASE / "host_vars/lada.yml").read_text())
        special = yaml.safe_load((BASE / "host_vars/vm-linux.yml").read_text())
        self.assertEqual(defaults["guardian_mode"], "temporary")
        self.assertFalse(defaults["guardian_camouflage"])
        self.assertFalse(regular["guardian_enabled"])
        self.assertNotIn("guardian_mode", regular)
        self.assertNotIn("guardian_camouflage", regular)
        self.assertTrue(special["guardian_enabled"])
        self.assertEqual(special["guardian_mode"], "permanent")
        self.assertTrue(special["guardian_camouflage"])
        self.assertEqual(special["guardian_provider"], "codex")

    def test_vm_linux_protected_runtime_is_not_managed_or_removed_by_guardian_role(self):
        tasks = yaml.safe_load((BASE / "roles/guardian/tasks/main.yml").read_text())
        serialized = (BASE / "roles/guardian/tasks/main.yml").read_text()
        runtime = (BASE / "roles/guardian/files/guardian").read_text()
        self.assertIn('os.urandom(random.randint(100, 600))', runtime)
        self.assertIn('random.uniform(0.5, 3)', runtime)
        for protected_path in (
            ".config/systemd/user/agent-mailbox-worker",
            "/etc/systemd/system/guardian.service.d",
            "/etc/systemd/system/agent-mailbox-worker",
        ):
            self.assertNotIn(protected_path, serialized)
        copied_units = [
            task["ansible.builtin.copy"]["dest"]
            for task in tasks
            if isinstance(task, dict) and "ansible.builtin.copy" in task
            and task["ansible.builtin.copy"].get("src") == "guardian.service"
        ]
        self.assertEqual(copied_units, ["/etc/systemd/system/guardian.service"])
        self.assertNotIn("wstunnel", serialized)

    def test_vm_linux_guardian_ciphertext_has_nas_and_station_recipients(self):
        encrypted = yaml.safe_load((BASE / "host_vars/vm-linux.sops.yaml").read_text())
        self.assertEqual(set(encrypted) - {"sops"}, {"hmac_key", "relay_url", "allowed_signers"})
        self.assertTrue(all(encrypted[key].startswith("ENC[") for key in ("hmac_key", "relay_url", "allowed_signers")))
        recipients = {item["recipient"] for item in encrypted["sops"]["age"]}
        self.assertEqual(recipients, {
            "age1wvl3m4stf3rccpt634jlvyyqlqaqexnq39egzxg7870hexehz37syw7ffx",
            "age1qzvj7dpclfwe7exs7hhmmce2xfdl7u3f430efnlzha9c8pdtm3yqh24an2",
        })

    def test_vendored_runtime_contains_fixes(self):
        text = (BASE / "roles/guardian/files/guardian").read_text()
        for marker in ("next_cycle_delay", "station_identity", "busy"):
            self.assertIn(marker, text, marker)
        self.assertIn('configured_provider == "none"', text)
        self.assertNotIn("UPGRADE_GUARDIAN", text)

    def test_none_provider_is_default_and_skips_agent_setup(self):
        defaults = (BASE / "roles/guardian/defaults/main.yml").read_text()
        tasks = (BASE / "roles/guardian/tasks/main.yml").read_text()
        validation = (BASE / "roles/guardian/tasks/validate-secrets.yml").read_text()
        self.assertIn("guardian_provider: none", defaults)
        self.assertIn("ansible.builtin.include_tasks: validate-secrets.yml", tasks)
        self.assertIn("guardian_provider in ['none', 'codex', 'claude']", validation)
        self.assertIn("guardian_enabled | bool and guardian_provider != 'none'", tasks)
        self.assertIn("agent_provider: \"{{ guardian_provider }}\"", tasks)
        self.assertIn("guardian_provider == 'none'", tasks)
        self.assertIn("guardian_mode: temporary", defaults)
        self.assertIn("guardian_camouflage: false", defaults)
        self.assertIn('mode: "{{ guardian_mode }}"', tasks)
        self.assertIn('camouflage: "{{ guardian_camouflage | bool }}"', tasks)
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

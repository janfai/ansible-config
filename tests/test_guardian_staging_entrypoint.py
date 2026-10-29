import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class GuardianStagingEntrypoint(unittest.TestCase):
    def test_guardian_entrypoint_is_vm_linux_only_and_does_not_load_generic_mail_secrets(self):
        play = yaml.safe_load((BASE / "guardian-vm-linux.yml").read_text())[0]
        serialized = (BASE / "guardian-vm-linux.yml").read_text()
        roles = play["roles"]
        self.assertEqual([role["role"] for role in roles], ["guardian"])
        self.assertNotIn("secrets/vm-linux.enc.yaml", serialized)
        for name in (
            "SMTP_RELAY_HOST",
            "SMTP_PASS_VM_LINUX",
            "USER_EMAIL",
            "ADMIN_EMAIL",
            "SMTP_ACCOUNT",
            "ADMIN_SIGNATURE",
        ):
            self.assertNotIn(name, serialized)
        tasks = play["pre_tasks"]
        self.assertTrue(any(task.get("name") == "Ověřit cílový systém a identitu vm-linux" for task in tasks))
        self.assertTrue(any(task.get("name") == "Ověřit root-only age identitu" for task in tasks))
        guardian = roles[0]
        self.assertIn("station_config.guardian_mode", guardian["guardian_mode"])
        self.assertIn("station_config.guardian_camouflage", guardian["guardian_camouflage"])

    def test_regular_local_playbook_still_requires_generic_station_secrets_by_default(self):
        play = yaml.safe_load((BASE / "local.yml").read_text())[0]
        tasks = play["pre_tasks"]
        load = next(task for task in tasks if task.get("name") == "Načíst šifrovaná tajemství stanice")
        validate = next(task for task in tasks if task.get("name") == "Ověřit povinná tajemství")
        self.assertNotIn("when", load)
        self.assertNotIn("when", validate)
        self.assertIn("secrets/", str(load))
        for name in (
            "SMTP_RELAY_HOST",
            "SMTP_PASS_",
            "USER_EMAIL",
            "ADMIN_EMAIL",
            "SMTP_ACCOUNT",
            "ADMIN_SIGNATURE",
        ):
            self.assertIn(name, str(validate))

    def test_guardian_only_role_has_no_smtp_dependency_and_keeps_special_profile(self):
        host = yaml.safe_load((BASE / "host_vars/vm-linux.yml").read_text())
        defaults = yaml.safe_load((BASE / "roles/guardian/defaults/main.yml").read_text())
        self.assertTrue(host["guardian_enabled"])
        self.assertEqual(host["guardian_mode"], "permanent")
        self.assertTrue(host["guardian_camouflage"])
        self.assertEqual(defaults["guardian_mode"], "temporary")
        self.assertFalse(defaults["guardian_camouflage"])
        role_text = "\n".join(path.read_text() for path in (BASE / "roles/guardian/tasks").glob("*.yml"))
        self.assertNotIn("SMTP_RELAY_HOST", role_text)
        self.assertNotIn("SMTP_ACCOUNT", role_text)
        self.assertNotIn("station_secrets", role_text)
        runtime = (BASE / "roles/guardian/files/guardian").read_text()
        self.assertIn("os.urandom(random.randint(100, 600))", runtime)
        self.assertIn("random.uniform(0.5, 3)", runtime)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_guardian_entrypoint_passes_ansible_syntax_check_without_generic_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(BASE / "guardian-vm-linux.yml", root / "guardian-vm-linux.yml")
            shutil.copy2(BASE / "ansible.cfg", root / "ansible.cfg")
            shutil.copytree(BASE / "group_vars", root / "group_vars")
            (root / "host_vars").mkdir()
            shutil.copy2(BASE / "host_vars/vm-linux.yml", root / "host_vars/vm-linux.yml")
            (root / "roles").symlink_to(BASE / "roles", target_is_directory=True)
            (root / "collections").symlink_to(BASE / "collections", target_is_directory=True)
            self.assertFalse((root / "secrets/vm-linux.enc.yaml").exists())
            result = subprocess.run(
                ["ansible-playbook", "--syntax-check", "guardian-vm-linux.yml"],
                cwd=root,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

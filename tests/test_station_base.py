import subprocess
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
ROLE = BASE / "roles/station_base"


class StationBase(unittest.TestCase):
    def setUp(self):
        self.tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        self.defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())

    def test_role_is_in_station_playbook_after_common(self):
        playbook = yaml.safe_load((BASE / "local.yml").read_text())
        roles = [r if isinstance(r, str) else r["role"] for r in playbook[0]["roles"]]
        self.assertEqual(roles.index("station_base"), roles.index("common") + 1)

    def test_conflicting_time_services_are_purged_and_timesyncd_ensured(self):
        self.assertEqual(self.defaults["station_base_conflicting_time_packages"], ["ntp", "chrony", "ntpsec"])
        purge = [t for t in self.tasks if t.get("ansible.builtin.apt", {}).get("state") == "absent"]
        self.assertEqual(len(purge), 1)
        self.assertTrue(purge[0]["ansible.builtin.apt"]["purge"])
        units = [t["ansible.builtin.systemd"] for t in self.tasks if "ansible.builtin.systemd" in t]
        timesyncd = [u for u in units if u["name"] == "systemd-timesyncd.service"][0]
        self.assertTrue(timesyncd["enabled"])
        self.assertEqual(timesyncd["state"], "started")

    def test_casper_md5check_is_masked(self):
        units = [t["ansible.builtin.systemd"] for t in self.tasks if "ansible.builtin.systemd" in t]
        casper = [u for u in units if u["name"] == "casper-md5check.service"][0]
        self.assertTrue(casper["masked"])
        self.assertFalse(casper["enabled"])

    def test_legacy_udev_rules_are_backed_up_before_removal(self):
        names = [t["name"] for t in self.tasks]
        backup = names.index("Zálohovat nebalíčková stará pravidla udev")
        remove = names.index("Odsunout nebalíčková stará pravidla udev")
        self.assertLess(backup, remove)
        copy = self.tasks[backup]["ansible.builtin.copy"]
        self.assertTrue(copy["remote_src"])
        self.assertFalse(copy["force"])

    def test_services_do_not_install_packages_or_touch_third_party(self):
        text = (ROLE / "tasks/main.yml").read_text()
        for forbidden in ("teamviewer", "openvpn", "timeshift", "skype"):
            self.assertNotIn(forbidden, text)
        for entry in self.defaults["station_base_services"]:
            self.assertNotIn("cups-browsed", entry["unit"])
        installs = [t for t in self.tasks if t.get("ansible.builtin.apt", {}).get("state") == "present"]
        self.assertEqual([t["ansible.builtin.apt"]["name"] for t in installs], ["systemd-timesyncd"])

    def test_resume_is_owned_only_by_common(self):
        self.assertNotIn("RESUME", (ROLE / "tasks/main.yml").read_text())
        self.assertIn("RESUME=", (BASE / "roles/common/tasks/main.yml").read_text())

    def test_syntax_check(self):
        result = subprocess.run(
            ["ansible-playbook", "--syntax-check", "local.yml"],
            cwd=BASE, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

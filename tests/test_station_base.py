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

    def test_absent_packages_are_passed_from_station_config(self):
        playbook = yaml.safe_load((BASE / "local.yml").read_text())
        role = next(r for r in playbook[0]["roles"] if not isinstance(r, str) and r["role"] == "station_base")
        self.assertIn("station_config.station_base_absent_packages", role["station_base_absent_packages"])
        lada = yaml.safe_load((BASE / "host_vars/lada.yml").read_text())
        for package in ("openvpn", "virtualbox", "virtualbox-qt", "virtualbox-dkms"):
            self.assertIn(package, lada["station_base_absent_packages"])

    def test_conflicting_time_services_are_purged_and_timesyncd_ensured(self):
        self.assertEqual(self.defaults["station_base_conflicting_time_packages"], ["ntp", "chrony", "ntpsec"])
        purge = next(t for t in self.tasks if t.get("name") == "Odstranit konkurenční časové služby včetně konfigurace")
        self.assertTrue(purge["ansible.builtin.apt"]["purge"])
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
        for forbidden in ("timeshift", "skype"):
            self.assertNotIn(forbidden, text)
        for entry in self.defaults["station_base_services"]:
            self.assertNotIn("cups-browsed", entry["unit"])
        installs = [t for t in self.tasks if t.get("ansible.builtin.apt", {}).get("state") == "present"]
        self.assertEqual([t["ansible.builtin.apt"]["name"] for t in installs], ["systemd-timesyncd"])

    def test_optional_removal_is_guarded_and_default_is_empty(self):
        self.assertEqual(self.defaults["station_base_absent_packages"], [])
        safety = next(t for t in self.tasks if t.get("name") == "Prověřit bezpečné odstranění volitelných balíčků")
        remove = next(t for t in self.tasks if t.get("name") == "Odstranit volitelné balíčky bez aktivní konfigurace OpenVPN")
        self.assertFalse(safety["check_mode"])
        self.assertEqual(remove["ansible.builtin.apt"]["state"], "absent")
        self.assertTrue(remove["ansible.builtin.apt"]["purge"])
        self.assertTrue(remove["ansible.builtin.apt"]["autoremove"])
        self.assertEqual(remove["when"][1:], ["'conf=none' in station_base_openvpn_safety.stdout_lines", "'vpn=no' in station_base_openvpn_safety.stdout_lines", "'process=no' in station_base_openvpn_safety.stdout_lines"])
        command = safety["ansible.builtin.command"]["argv"][-1]
        self.assertIn("/etc/openvpn/client", command)
        self.assertIn("/etc/openvpn/server", command)
        self.assertIn("nmcli -t -f TYPE connection show", command)
        self.assertIn("pgrep -x openvpn", command)
        self.assertNotIn("network-manager'", remove["ansible.builtin.apt"]["name"])

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

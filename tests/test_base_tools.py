import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
ROLE = BASE / "roles/base_tools"


class BaseTools(unittest.TestCase):
    def test_default_tools_cover_standard_set(self):
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        packages = set(defaults["base_tools_packages"])
        for tool in ("htop", "btop", "atop", "iotop", "iftop", "iptraf-ng", "mc", "nmap", "vim", "ncdu", "needrestart", "smartmontools", "lm-sensors"):
            self.assertIn(tool, packages)
        self.assertEqual(len(packages), len(defaults["base_tools_packages"]))
        for forbidden in ("ntp", "chrony", "hddtemp", "openvpn", "virtualbox"):
            self.assertNotIn(forbidden, packages)

    def test_role_is_enabled_by_default_and_passed_from_station_config(self):
        playbook = yaml.safe_load((BASE / "local.yml").read_text())
        role = next(r for r in playbook[0]["roles"] if not isinstance(r, str) and r["role"] == "base_tools")
        self.assertIn("station_config.base_tools_enabled | default(true)", role["base_tools_enabled"])
        names = [r if isinstance(r, str) else r["role"] for r in playbook[0]["roles"]]
        self.assertLess(names.index("base_tools"), names.index("station_base"))

    def test_needrestart_does_not_restart_services_automatically(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        needrestart = next(t for t in tasks if "needrestart" in t["name"].lower())
        self.assertIn("'l'", needrestart["ansible.builtin.copy"]["content"])


if __name__ == "__main__":
    unittest.main()

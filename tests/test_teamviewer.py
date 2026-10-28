import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class TeamViewer(unittest.TestCase):
    def test_role_is_opt_in_and_uses_stable_signed_repository(self):
        defaults = yaml.safe_load((BASE / "roles/teamviewer/defaults/main.yml").read_text())
        tasks = yaml.safe_load((BASE / "roles/teamviewer/tasks/main.yml").read_text())
        self.assertFalse(defaults["teamviewer_enabled"])
        repo = next(t["ansible.builtin.copy"] for t in tasks if "ansible.builtin.copy" in t)
        self.assertIn("signed-by=/usr/share/keyrings/teamviewer-keyring.gpg", repo["content"])
        self.assertIn("/deb stable main", repo["content"])
        repo_task = next(t for t in tasks if "teamviewer.list" in t.get("ansible.builtin.copy", {}).get("dest", ""))
        self.assertEqual(repo_task["register"], "teamviewer_repository")
        cache_task = next(t for t in tasks if t.get("name") == "Obnovit indexy po změně repozitáře TeamVieweru")
        self.assertIn("teamviewer_repository.changed", cache_task["when"])
        self.assertIn("not ansible_check_mode", cache_task["when"])
        package_task = next(t for t in tasks if t.get("ansible.builtin.apt", {}).get("name") == "teamviewer")
        package = package_task["ansible.builtin.apt"]
        self.assertEqual(package, {"name": "teamviewer", "state": "latest", "update_cache": True, "cache_valid_time": 3600})
        self.assertIn("not ansible_check_mode", package_task["when"])
        unattended = next(t["ansible.builtin.copy"] for t in tasks if t.get("ansible.builtin.copy", {}).get("dest", "").endswith("52teamviewer-unattended-upgrades"))
        self.assertIn('origin=TeamViewer GmbH,label=TeamViewer', unattended["content"])
        self.assertEqual(unattended["mode"], "0644")
        service = next(t["ansible.builtin.systemd"] for t in tasks if "ansible.builtin.systemd" in t)
        self.assertEqual(service, {"name": "teamviewerd.service", "enabled": True, "state": "started"})
        self.assertTrue(all("teamviewer_enabled | bool" in (t.get("when") if isinstance(t.get("when"), list) else [t.get("when")]) for t in tasks))

    def test_station_configuration_is_opted_in_and_role_is_included(self):
        host = yaml.safe_load((BASE / "host_vars/lada.yml").read_text())
        playbook = yaml.safe_load((BASE / "local.yml").read_text())
        roles = playbook[0]["roles"]
        teamviewer = next(r for r in roles if isinstance(r, dict) and r.get("role") == "teamviewer")
        self.assertTrue(host["teamviewer_enabled"])
        self.assertEqual(host["station_base_absent_packages"], ["network-manager-openvpn-gnome", "network-manager-openvpn", "openvpn", "virtualbox-qt", "virtualbox-dkms", "virtualbox"])
        self.assertEqual(teamviewer["teamviewer_enabled"], "{{ station_config.teamviewer_enabled | default(false) }}")


if __name__ == "__main__":
    unittest.main()

import getpass
import grp
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class GuardianHomeLaptop(unittest.TestCase):
    def run_fixture(self, *, hostname="home-laptop", distribution="Archlinux"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(BASE / "guardian-home-laptop.yml", root / "guardian-home-laptop.yml")
            (root / "host_vars").mkdir()
            shutil.copy2(BASE / "host_vars/home-laptop.yml", root / "host_vars/home-laptop.yml")
            role = root / "roles/guardian/tasks"
            role.mkdir(parents=True)
            marker = root / "role-ran"
            (role / "main.yml").write_text(
                f"- name: Record role execution\n  ansible.builtin.copy:\n    content: reached\n    dest: {marker}\n"
            )
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    "localhost,",
                    "guardian-home-laptop.yml",
                    "-e",
                    json.dumps({"ansible_hostname": hostname, "ansible_distribution": distribution}),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            return result, marker.exists()

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_only_omarchy_home_laptop_reaches_guardian_role(self):
        result, role_ran = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(role_ran, result.stdout + result.stderr)

        for hostname, distribution in (("other-host", "Archlinux"), ("home-laptop", "Ubuntu")):
            with self.subTest(hostname=hostname, distribution=distribution):
                result, role_ran = self.run_fixture(hostname=hostname, distribution=distribution)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Tento vstupní bod je určen pouze pro home-laptop s Arch Linuxem.", result.stdout)
                self.assertFalse(role_ran, result.stdout + result.stderr)

    def test_host_profile_is_permanent_with_documented_generic_defaults(self):
        config = yaml.safe_load((BASE / "host_vars/home-laptop.yml").read_text())
        self.assertTrue(config["guardian_enabled"])
        self.assertTrue(config["guardian_git_enabled"])
        self.assertEqual(config["guardian_station_id"], "home-laptop")
        self.assertEqual(config["guardian_mode"], "permanent")
        self.assertEqual(config["guardian_provider"], "none")
        self.assertFalse(config["guardian_camouflage"])
        play = yaml.safe_load((BASE / "guardian-home-laptop.yml").read_text())[0]
        self.assertEqual([role["role"] for role in play["roles"]], ["guardian"])

    @unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("ssh-keygen"), "Ansible nebo ssh-keygen není nainstalován")
    def test_station_key_is_create_only_and_private_material_stays_out_of_reports(self):
        source = yaml.safe_load((BASE / "roles/guardian/tasks/git-mailbox.yml").read_text())
        generate = next(task for task in source if task.get("name") == "Vygenerovat staniční klíč pouze na stanici")
        self.assertEqual(generate["ansible.builtin.command"]["creates"], "/etc/guardian/station_ed25519")
        restore = next(task for task in source if task.get("name") == "Obnovit staniční klíč z šifrované zálohy, pokud chybí")
        self.assertFalse(restore["ansible.builtin.copy"]["force"])
        self.assertEqual(restore["ansible.builtin.copy"]["owner"], "root")
        self.assertEqual(restore["ansible.builtin.copy"]["group"], "root")
        self.assertEqual(restore["ansible.builtin.copy"]["mode"], "0600")
        self.assertTrue(restore["no_log"])

        names = {
            "Vygenerovat staniční klíč pouze na stanici",
            "Zajistit existenci veřejné části staničního klíče",
            "Chránit staniční privátní klíč",
            "Chránit veřejnou část staničního klíče",
        }
        tasks = [task for task in source if task.get("name") in names]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "station_ed25519"
            play = yaml.safe_dump(
                [{"name": "key fixture", "hosts": "localhost", "connection": "local", "tasks": tasks}],
                allow_unicode=True,
            )
            play = play.replace("/etc/guardian/station_ed25519", str(key))
            play = play.replace("owner: root", f"owner: {getpass.getuser()}")
            play = play.replace("group: root", f"group: {grp.getgrgid(os.getgid()).gr_name}")
            play_path = root / "key-fixture.yml"
            play_path.write_text(play)
            for _ in range(2):
                result = subprocess.run(
                    ["ansible-playbook", "-i", "localhost,", str(play_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn(key.read_text(), result.stdout + result.stderr)
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                self.assertEqual(key.stat().st_uid, os.getuid())

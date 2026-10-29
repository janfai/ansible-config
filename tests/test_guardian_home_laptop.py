import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
FIXTURE_CIPHERTEXT = b"SOPS-ENCRYPTED-FIXTURE-NOT-A-REAL-SECRET\n"
FIXTURE_PRIVATE_KEY = "FIXTURE-PRIVATE-KEY-NOT-A-REAL-KEY\n"
FIXTURE_SECRETS = {
    "relay_url": "https://relay.invalid/fixture",
    "hmac_key": "fixture-hmac-value-not-a-real-key-000000",
    "allowed_signers": "fixture-signer-entry",
    "station_ssh_private_key": FIXTURE_PRIVATE_KEY,
}


class GuardianHomeLaptop(unittest.TestCase):
    def create_entrypoint_fixture(self, root, role_main):
        shutil.copy2(BASE / "guardian-home-laptop.yml", root / "guardian-home-laptop.yml")
        shutil.copy2(BASE / "ansible.cfg", root / "ansible.cfg")
        (root / "host_vars").mkdir()
        shutil.copy2(BASE / "host_vars/home-laptop.yml", root / "host_vars/home-laptop.yml")
        role = root / "roles/guardian/tasks"
        role.mkdir(parents=True)
        (role / "main.yml").write_text(role_main)
        defaults = root / "roles/guardian/defaults"
        defaults.mkdir()
        shutil.copy2(BASE / "roles/guardian/defaults/main.yml", defaults / "main.yml")

    def run_entrypoint(self, root, extra_vars=None, env=None):
        variables = {"ansible_hostname": "home-laptop", "ansible_distribution": "Archlinux"}
        variables.update(extra_vars or {})
        process_env = os.environ.copy()
        process_env["ANSIBLE_LOOKUP_PLUGINS"] = str(BASE / "lookup_plugins")
        process_env.update(env or {})
        return subprocess.run(
            ["ansible-playbook", "-i", "localhost,", "guardian-home-laptop.yml", "-e", json.dumps(variables)],
            cwd=root,
            env=process_env,
            text=True,
            capture_output=True,
            check=False,
        )

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_only_omarchy_home_laptop_reaches_guardian_role(self):
        for hostname, distribution, expected in (
            ("home-laptop", "Archlinux", True),
            ("other-host", "Archlinux", False),
            ("home-laptop", "Ubuntu", False),
        ):
            with self.subTest(hostname=hostname, distribution=distribution), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                marker = root / "role-ran"
                self.create_entrypoint_fixture(
                    root,
                    f"- name: Record role execution\n  ansible.builtin.copy:\n    content: reached\n    dest: {marker}\n",
                )
                result = self.run_entrypoint(root, {"ansible_hostname": hostname, "ansible_distribution": distribution})
                self.assertEqual(marker.exists(), expected, result.stdout + result.stderr)
                self.assertEqual(result.returncode == 0, expected, result.stdout + result.stderr)
                if not expected:
                    self.assertIn("Tento vstupní bod je určen pouze pro home-laptop s Arch Linuxem.", result.stdout)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_extra_vars_cannot_redirect_station_or_guardian_identity(self):
        for override in ("station_id", "guardian_station_id"):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                marker = root / "role-ran"
                self.create_entrypoint_fixture(
                    root,
                    f"- name: Record role execution\n  ansible.builtin.copy:\n    content: reached\n    dest: {marker}\n",
                )
                result = self.run_entrypoint(root, {override: "vm-linux"})
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Identita vstupního bodu musí zůstat home-laptop.", result.stdout)
                self.assertFalse(marker.exists(), result.stdout + result.stderr)

    def test_host_profile_is_permanent_with_documented_generic_defaults(self):
        config = yaml.safe_load((BASE / "host_vars/home-laptop.yml").read_text())
        self.assertTrue(config["guardian_enabled"])
        self.assertTrue(config["guardian_git_enabled"])
        self.assertEqual(config["guardian_station_id"], "home-laptop")
        self.assertEqual(config["guardian_mode"], "permanent")
        self.assertEqual(config["guardian_provider"], "none")
        self.assertFalse(config["guardian_camouflage"])
        self.assertFalse((BASE / "host_vars/home-laptop.sops.yaml").exists())
        self.assertEqual(config["guardian_ssh_target"], "jan@home-laptop")
        play_vars = yaml.safe_load((BASE / "guardian-home-laptop.yml").read_text())[0]["vars"]
        self.assertFalse(play_vars["guardian_gate_enrollment_enabled"])
        self.assertIn("Work/bin/guardian-git-enroll", play_vars["guardian_gate_enroll_bin"])
        self.assertIn(".ssh/id_ed25519.pub", play_vars["guardian_gate_master_public_key"])

    def test_remote_sops_transport_is_limited_to_home_laptop(self):
        tasks = yaml.safe_load((BASE / "roles/guardian/tasks/load-secrets.yml").read_text())
        remote = next(task for task in tasks if "home-nas" in task["name"])
        local = next(task for task in tasks if "ostatních stanic" in task["name"])
        self.assertIn("guardian_station_id == 'home-laptop'", remote["when"])
        self.assertIn("guardian_station_id != 'home-laptop'", local["when"])
        self.assertIn("community.sops.sops", local["ansible.builtin.set_fact"]["guardian_secrets"])

    @unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("sudo"), "Ansible nebo sudo není nainstalován")
    def test_station_key_fixture_restores_root_owned_without_overwriting(self):
        source = yaml.safe_load((BASE / "roles/guardian/tasks/git-mailbox.yml").read_text())
        restore = next(task for task in source if task.get("name") == "Obnovit staniční klíč z šifrované zálohy, pokud chybí")
        self.assertFalse(restore["ansible.builtin.copy"]["force"])
        self.assertEqual(restore["ansible.builtin.copy"]["owner"], "root")
        self.assertEqual(restore["ansible.builtin.copy"]["group"], "root")
        self.assertEqual(restore["ansible.builtin.copy"]["mode"], "0600")
        self.assertTrue(restore["no_log"])
        self.assertEqual(
            next(task for task in source if task.get("name") == "Vygenerovat staniční klíč pouze na stanici")["ansible.builtin.command"]["creates"],
            "/etc/guardian/station_ed25519",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "station_ed25519"
            variables = root / "fixture-vars.json"
            play_path = root / "key-fixture.yml"
            task = yaml.safe_load(yaml.safe_dump(restore))
            task["ansible.builtin.copy"]["dest"] = str(key)
            play_path.write_text(yaml.safe_dump([{
                "name": "station key fixture",
                "hosts": "localhost",
                "connection": "local",
                "become": True,
                "become_flags": "-n",
                "tasks": [task],
            }]))
            for fixture in (FIXTURE_PRIVATE_KEY, "DIFFERENT-FIXTURE-MUST-NOT-REPLACE-EXISTING\n"):
                variables.write_text(json.dumps({"guardian_secrets": {"station_ssh_private_key": fixture}}))
                result = subprocess.run(
                    ["ansible-playbook", "-i", "localhost,", str(play_path), "-e", "@" + str(variables)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn(FIXTURE_PRIVATE_KEY, result.stdout + result.stderr)
                self.assertEqual(key.stat().st_uid, 0)
                self.assertEqual(key.stat().st_gid, 0)
                self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                stored = subprocess.check_output(["sudo", "-n", "cat", str(key)], text=True)
                self.assertEqual(stored, FIXTURE_PRIVATE_KEY)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_remote_sops_lookup_hands_fixture_to_actual_role_validation_without_plaintext_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            role_main = "\n".join([
                "- ansible.builtin.include_tasks: " + str(BASE / "roles/guardian/tasks/load-secrets.yml"),
                "- ansible.builtin.include_tasks: " + str(BASE / "roles/guardian/tasks/validate-secrets.yml"),
                "- name: Verify home-laptop role variable handoff",
                "  ansible.builtin.assert:",
                "    that:",
                "      - guardian_enabled | bool",
                "      - guardian_station_id == 'home-laptop'",
                "      - guardian_provider == 'none'",
                "      - guardian_mode == 'permanent'",
                "      - not guardian_camouflage | bool",
                "      - guardian_relay_url == guardian_secrets.relay_url",
                "    fail_msg: laptop role variable handoff failed",
                "  no_log: true",
            ]) + "\n"
            self.create_entrypoint_fixture(root, role_main)
            (root / "host_vars/home-laptop.sops.yaml").write_bytes(FIXTURE_CIPHERTEXT)
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            ssh = fake_bin / "ssh"
            ssh.write_text("\n".join([
                "#!/usr/bin/env python3",
                "import base64, os, sys",
                "args = sys.argv[1:]",
                "command = args[-1] if args else ''",
                "if 'home-nas' not in args or 'StrictHostKeyChecking=yes' not in args or 'SOPS_AGE_KEY_FILE=/mnt/disk-pool/secrets/key.txt' not in command or '/dev/stdin' not in command:",
                "    sys.exit(71)",
                "if sys.stdin.buffer.read() != b'SOPS-ENCRYPTED-FIXTURE-NOT-A-REAL-SECRET\\n':",
                "    sys.exit(72)",
                "sys.stdout.buffer.write(base64.b64decode(os.environ['FIXTURE_SOPS_OUTPUT']))",
            ]) + "\n")
            ssh.chmod(0o755)
            fixture_yaml = yaml.safe_dump(FIXTURE_SECRETS)
            result = self.run_entrypoint(
                root,
                env={
                    "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
                    "FIXTURE_SOPS_OUTPUT": base64.b64encode(fixture_yaml.encode()).decode(),
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(FIXTURE_SECRETS["hmac_key"], result.stdout + result.stderr)
            self.assertNotIn(FIXTURE_SECRETS["station_ssh_private_key"], result.stdout + result.stderr)
            for path in root.rglob("*"):
                if path.is_file():
                    contents = path.read_bytes()
                    self.assertNotIn(FIXTURE_SECRETS["hmac_key"].encode(), contents)
                    self.assertNotIn(FIXTURE_SECRETS["station_ssh_private_key"].encode(), contents)

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook není nainstalován")
    def test_gate_enrollment_is_explicit_strict_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "role-ran"
            self.create_entrypoint_fixture(
                root,
                f"- name: Record role execution\n  ansible.builtin.copy:\n    content: reached\n    dest: {marker}\n",
            )
            fake_helper = root / "guardian-git-enroll-fixture"
            trace = root / "helper-calls.jsonl"
            fake_helper.write_text("\n".join([
                "#!/usr/bin/env python3",
                "import json, sys",
                "from pathlib import Path",
                "trace = Path(" + repr(str(trace)) + ")",
                "calls = trace.read_text().splitlines() if trace.exists() else []",
                "with trace.open('a') as stream: stream.write(json.dumps(sys.argv[1:]) + '\\n')",
                "print(json.dumps({'added_keys': 1 if not calls else 0}))",
            ]) + "\n")
            fake_helper.chmod(0o755)
            disabled = self.run_entrypoint(root)
            self.assertEqual(disabled.returncode, 0, disabled.stdout + disabled.stderr)
            self.assertFalse(trace.exists())

            extra = {
                "guardian_gate_enrollment_enabled": True,
                "guardian_gate_enroll_bin": str(fake_helper),
                "guardian_gate_master_public_key": str(root / "master.pub"),
            }
            first = self.run_entrypoint(root, extra)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = self.run_entrypoint(root, extra)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("changed=0", second.stdout)
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            for args in calls:
                self.assertEqual(args[args.index("--id") + 1], "home-laptop")
                self.assertEqual(args[args.index("--station") + 1], "jan@home-laptop")
                self.assertEqual(args[args.index("--master-name") + 1], "home-laptop")
                self.assertEqual(args[args.index("--ssh-option") + 1], "StrictHostKeyChecking=yes")
                self.assertNotIn("--dry-run", args)


if __name__ == "__main__":
    unittest.main()

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

BASE = Path(__file__).resolve().parents[1]
UPDATER = BASE / "roles/guardian_relay_enrollment/files/relay-enroll.py"
FIXTURE_KEY = b"fixture-only-hmac-value-not-a-real-key\n"


class RelayEnrollment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "relay.json"
        self.key = self.root / "stations/home-laptop.key"
        existing_keys = self.root / "stations"
        existing_keys.mkdir()
        (existing_keys / "lada.key").write_bytes(b"fixture-key-for-lada\n")
        (existing_keys / "vm-linux.key").write_bytes(b"fixture-key-for-vm-linux\n")
        self.initial = {
            "database": "/var/lib/guardian-relay/relay.db",
            "legacy_station_id": "lada",
            "station_key_files": {
                "lada": str(existing_keys / "lada.key"),
                "vm-linux": str(existing_keys / "vm-linux.key"),
            },
        }
        self.config.write_text(json.dumps(self.initial) + "\n")
        self.config.chmod(0o600)

    def tearDown(self):
        self.temp.cleanup()

    def run_updater(self, payload=FIXTURE_KEY):
        return subprocess.run(
            [sys.executable, str(UPDATER), str(self.config), "home-laptop", str(self.key)],
            input=payload,
            capture_output=True,
            check=False,
        )

    def run_updater(self, payload=FIXTURE_KEY):
        source = UPDATER.read_text()
        test_updater = self.root / "relay-enroll.py"
        source = source.replace('grp.getgrnam("guardian-relay").gr_gid', "os.getgid()")
        source = source.replace("os.fchown(stream.fileno(), 0, os.getgid())", "os.fchown(stream.fileno(), os.getuid(), os.getgid())")
        test_updater.write_text(source)
        return subprocess.run(
            [sys.executable, str(test_updater), str(self.config), "home-laptop", str(self.key)],
            input=payload,
            capture_output=True,
            check=False,
        )

    def test_adds_missing_key_and_mapping_without_changing_existing_entries(self):
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"changed\n")
        self.assertEqual(self.key.read_bytes(), FIXTURE_KEY)
        self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
        updated = json.loads(self.config.read_text())
        self.assertEqual(updated["station_key_files"]["home-laptop"], str(self.key))
        self.assertEqual(updated["station_key_files"]["lada"], self.initial["station_key_files"]["lada"])
        self.assertEqual(updated["station_key_files"]["vm-linux"], self.initial["station_key_files"]["vm-linux"])
        self.assertEqual(updated["legacy_station_id"], "lada")

    def test_does_not_overwrite_existing_station_key(self):
        self.key.parent.mkdir(parents=True, exist_ok=True)
        self.key.write_bytes(b"different-fixture-key\n")
        result = self.run_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.key.read_bytes(), b"different-fixture-key\n")
        self.assertNotIn(FIXTURE_KEY, result.stdout + result.stderr)

    def test_rejects_existing_station_mapping_to_another_path(self):
        self.initial["station_key_files"]["home-laptop"] = "/etc/guardian/stations/other.key"
        self.config.write_text(json.dumps(self.initial) + "\n")
        result = self.run_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), json.dumps(self.initial) + "\n")
        self.assertFalse(self.key.exists())

    def test_updater_rejects_duplicate_vm_linux_key_without_changes(self):
        vm_key = self.root / "stations/vm-linux.key"
        vm_key.parent.mkdir(parents=True, exist_ok=True)
        vm_key.write_bytes(FIXTURE_KEY)
        config_before = self.config.read_bytes()
        result = self.run_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"station key uniqueness check failed", result.stderr)
        self.assertNotIn(FIXTURE_KEY, result.stdout + result.stderr)
        self.assertEqual(self.config.read_bytes(), config_before)
        self.assertEqual(vm_key.read_bytes(), FIXTURE_KEY)
        self.assertFalse(self.key.exists())

    def test_second_run_is_idempotent(self):
        first = self.run_updater()
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = self.config.read_bytes()
        second = self.run_updater()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, b"ok\n")
        self.assertEqual(self.config.read_bytes(), after_first)

    def test_rejects_duplicate_vm_linux_key_before_any_changes(self):
        vm_key = Path(self.initial["station_key_files"]["vm-linux"])
        vm_key.write_bytes(FIXTURE_KEY)
        config_before = self.config.read_bytes()
        vm_key_before = vm_key.read_bytes()
        result = self.run_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"station key uniqueness check failed", result.stderr)
        self.assertNotIn(FIXTURE_KEY, result.stdout + result.stderr)
        self.assertEqual(self.config.read_bytes(), config_before)
        self.assertEqual(vm_key.read_bytes(), vm_key_before)
        self.assertFalse(self.key.exists())

    def test_skips_missing_mapped_station_key_file(self):
        missing = self.root / "stations/missing.key"
        self.initial["station_key_files"]["offline-station"] = str(missing)
        self.config.write_text(json.dumps(self.initial) + "\n")
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.key.read_bytes(), FIXTURE_KEY)

    def test_rejects_symlink_and_fifo_mapped_key_paths(self):
        target = self.root / "outside.key"
        target.write_bytes(b"different-fixture-key\n")
        symlink = self.root / "stations/symlink.key"
        symlink.symlink_to(target)
        fifo = self.root / "stations/fifo.key"
        os.mkfifo(fifo)
        for mapped_path in (symlink, fifo):
            with self.subTest(mapped_path=mapped_path.name):
                self.initial["station_key_files"]["unsafe-station"] = str(mapped_path)
                self.config.write_text(json.dumps(self.initial) + "\n")
                result = self.run_updater()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.key.exists())

    def test_normalizes_trailing_newlines_for_existing_key_equality(self):
        self.key.parent.mkdir(parents=True, exist_ok=True)
        self.key.write_bytes(FIXTURE_KEY.rstrip(b"\n") + b"\r\n\n")
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"changed\n")
        self.assertEqual(self.key.read_bytes(), FIXTURE_KEY.rstrip(b"\n") + b"\r\n\n")

    def test_normalizes_trailing_newlines_for_uniqueness_check(self):
        Path(self.initial["station_key_files"]["vm-linux"]).write_bytes(FIXTURE_KEY.rstrip(b"\n") + b"\r\n")
        config_before = self.config.read_bytes()
        result = self.run_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"station key uniqueness check failed", result.stderr)
        self.assertEqual(self.config.read_bytes(), config_before)
        self.assertFalse(self.key.exists())

    def test_refuses_missing_key_input_without_secret_output(self):
        result = self.run_updater(payload=b"")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(FIXTURE_KEY, result.stdout + result.stderr)

    def test_playbook_uses_native_strict_vps_inventory_and_no_staging_secret(self):
        inventory = (BASE / "inventories/vps.yml").read_text()
        playbook = (BASE / "relay-enroll-home-laptop.yml").read_text()
        parsed_playbook = yaml.safe_load(playbook)
        self.assertIn("ansible_user: jan", inventory)
        self.assertIn("ansible_port: 10022", inventory)
        self.assertIn("ansible_become: true", inventory)
        self.assertIn("ansible_become_flags: -n", inventory)
        expected_ssh = {
            "IdentityAgent": "/run/user/1000/ssh-agent.socket",
            "IdentityFile": "/home/jan/.ssh/id_ed25519_hetzner",
            "IdentitiesOnly": "yes",
            "UserKnownHostsFile": "/home/jan/.ssh/known_hosts",
            "StrictHostKeyChecking": "yes",
        }
        self.assertIn("ansible_host: vps", inventory)
        for option, value in expected_ssh.items():
            self.assertIn(f"-o {option}={value}", inventory)
        self.assertIn("guardian_sops_remote", playbook)
        self.assertIn("no_log: true", playbook)
        self.assertIn("relay_enroll_secret:", playbook)
        self.assertNotIn("content:", playbook)
        self.assertNotIn("stdin:", playbook)
        self.assertIn("plugins/action", (BASE / "ansible.cfg").read_text())
        self.assertIn("root", parsed_playbook[0]["tasks"][-1]["ansible.builtin.assert"]["that"][0])
        self.assertFalse((BASE / "host_vars/home-laptop.sops.yaml").exists())

    def test_fixture_key_is_only_passed_as_stdin_and_no_key_temp_file_is_created(self):
        before = set(self.root.rglob("*"))
        result = self.run_updater()
        after = set(self.root.rglob("*"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.key.read_bytes(), FIXTURE_KEY)
        self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
        self.assertFalse(any(path.is_file() and path != self.key and FIXTURE_KEY.rstrip() in path.read_bytes() for path in after - before))

    def test_action_plugin_uses_ssh_stdin_and_sanitizes_errors(self):
        action_source = (BASE / "plugins/action/relay_enroll_secret.py").read_text()
        self.assertIn("in_data=", action_source)
        self.assertIn("sudoable=True", action_source)
        self.assertNotIn("tempfile", action_source)
        self.assertNotIn("secret", action_source.split("command =", 1)[1].split("try:", 1)[0])
        self.assertIn('"Relay enrollment command failed."', action_source)
        self.assertIn("os.fchown", UPDATER.read_text())
        self.assertIn("os.fchmod", UPDATER.read_text())

    def test_action_plugin_sends_fixture_only_in_data_and_hides_remote_errors(self):
        from unittest.mock import patch
        from ansible.plugins.action import ActionBase

        spec = importlib.util.spec_from_file_location("relay_enroll_secret_test", BASE / "plugins/action/relay_enroll_secret.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        action = module.ActionModule.__new__(module.ActionModule)
        action._task = SimpleNamespace(args={
            "secret": FIXTURE_KEY.decode().strip(),
            "updater": "/opt/guardian/ansible/relay-enroll.py",
            "config_path": "/etc/guardian/relay.json",
            "station_id": "home-laptop",
            "key_path": "/etc/guardian/stations/home-laptop.key",
        })
        observed = {}

        def execute(command, in_data=None, sudoable=True):
            observed.update(command=command, in_data=in_data, sudoable=sudoable)
            return {"rc": 1, "stdout": "", "stderr": FIXTURE_KEY.decode()}

        action._low_level_execute_command = execute
        with patch.object(ActionBase, "run", return_value={}):
            result = action.run()
        self.assertEqual(observed["in_data"], FIXTURE_KEY)
        self.assertNotIn(FIXTURE_KEY.decode().strip(), observed["command"])
        self.assertTrue(observed["sudoable"])
        self.assertTrue(result["failed"])
        self.assertNotIn(FIXTURE_KEY.decode().strip(), result["msg"])
        self.assertNotIn(FIXTURE_KEY.decode().strip(), str(result))

    def test_action_plugin_accepts_dict_success_response(self):
        from unittest.mock import patch
        from ansible.plugins.action import ActionBase

        spec = importlib.util.spec_from_file_location("relay_enroll_secret_success_test", BASE / "plugins/action/relay_enroll_secret.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        action = module.ActionModule.__new__(module.ActionModule)
        action._task = SimpleNamespace(args={"secret": "fixture-only", "updater": "/updater", "config_path": "/config", "station_id": "station", "key_path": "/key"})
        action._low_level_execute_command = lambda *args, **kwargs: {"rc": 0, "stdout": "changed\n", "stderr": ""}
        with patch.object(ActionBase, "run", return_value={}):
            result = action.run()
        self.assertEqual(result, {"changed": True})

    def test_action_plugin_skips_check_mode_without_remote_execution(self):
        from unittest.mock import patch
        from ansible.plugins.action import ActionBase

        spec = importlib.util.spec_from_file_location("relay_enroll_secret_check_mode_test", BASE / "plugins/action/relay_enroll_secret.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        action = module.ActionModule.__new__(module.ActionModule)
        action._task = SimpleNamespace(args={})
        action._play_context = SimpleNamespace(check_mode=True)
        executed = []
        action._low_level_execute_command = lambda *args, **kwargs: executed.append((args, kwargs))
        with patch.object(ActionBase, "run", return_value={}):
            result = action.run()
        self.assertTrue(result["skipped"])
        self.assertFalse(result["changed"])
        self.assertEqual(executed, [])
        self.assertFalse(module.ActionModule._supports_check_mode)


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
UPDATER = BASE / "roles/guardian_relay_enrollment/files/relay-enroll.py"
FIXTURE_KEY = b"fixture-only-hmac-value-not-a-real-key\n"


class RelayEnrollment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "relay.json"
        self.key = self.root / "stations/home-laptop.key"
        self.initial = {
            "database": "/var/lib/guardian-relay/relay.db",
            "legacy_station_id": "lada",
            "station_key_files": {
                "lada": "/etc/guardian/stations/lada.key",
                "vm-linux": "/etc/guardian/stations/vm-linux.key",
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
        self.key.parent.mkdir(parents=True)
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

    def test_second_run_is_idempotent(self):
        first = self.run_updater()
        self.assertEqual(first.returncode, 0, first.stderr)
        after_first = self.config.read_bytes()
        second = self.run_updater()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, b"ok\n")
        self.assertEqual(self.config.read_bytes(), after_first)

    def test_refuses_missing_key_input_without_secret_output(self):
        result = self.run_updater(payload=b"")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(FIXTURE_KEY, result.stdout + result.stderr)

    def test_playbook_uses_native_strict_vps_inventory_and_no_staging_secret(self):
        inventory = (BASE / "inventories/vps.yml").read_text()
        playbook = (BASE / "relay-enroll-home-laptop.yml").read_text()
        self.assertIn("ansible_user: jan", inventory)
        self.assertIn("ansible_port: 10022", inventory)
        self.assertIn("ansible_become: true", inventory)
        self.assertIn("ansible_become_flags: -n", inventory)
        self.assertIn("StrictHostKeyChecking=yes", inventory)
        self.assertIn("guardian_sops_remote", playbook)
        self.assertIn("no_log: true", playbook)
        self.assertFalse((BASE / "host_vars/home-laptop.sops.yaml").exists())


if __name__ == "__main__":
    unittest.main()

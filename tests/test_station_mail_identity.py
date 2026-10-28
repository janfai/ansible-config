import importlib.util
import re
import subprocess
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("station_mail_identity", BASE / "roles/reporting/files/station_mail_identity.py")
IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IDENTITY)


class StationMailIdentity(unittest.TestCase):
    def test_identity_uses_primary_route_and_contains_all_fields(self):
        hostname = subprocess.CompletedProcess([], 0, "vm-mint.example.test\n", "")
        route = subprocess.CompletedProcess([], 0, "1.1.1.1 via 192.0.2.1 dev enp1s0 src 192.0.2.55 uid 0\n", "")
        with patch.object(IDENTITY.subprocess, "run", side_effect=[hostname, route]) as run:
            with patch.object(Path, "read_text", return_value="02:00:00:00:00:55\n"):
                lines = IDENTITY.station_identity("vm-mint").splitlines()
        self.assertEqual(lines[:4], ["Stanice: vm-mint", "Hostname: vm-mint.example.test", "IP: 192.0.2.55", "MAC: 02:00:00:00:00:55"])
        self.assertTrue(lines[4].startswith("Čas stanice: "))
        datetime.fromisoformat(lines[4][len("Čas stanice: "):])
        self.assertEqual(run.call_args_list[0].args[0], ["hostname", "-f"])
        self.assertEqual(run.call_args_list[1].args[0], ["ip", "-4", "route", "get", "1.1.1.1"])

    def test_all_reporting_mail_paths_and_guardian_say_include_identity(self):
        failed = (BASE / "roles/reporting/files/ansible-pull-failed").read_text()
        reporting = (BASE / "roles/reporting/files/reporting.py").read_text()
        guardian = (BASE / "roles/guardian/files/guardian").read_text()
        self.assertRegex(failed, re.compile(r"Subject: \[\{station_id\}\] Stanice nemohla stáhnout konfiguraci"))
        self.assertIn("{identity}", failed)
        self.assertIn("f'[{station}] {subject}'", reporting)
        self.assertIn("station_identity(station)", reporting)
        self.assertIn('"from": conf["id"]', guardian)
        self.assertIn('station_identity(conf["id"])', guardian)


if __name__ == "__main__":
    unittest.main()

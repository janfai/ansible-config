import importlib.util
import unittest
from pathlib import Path
from unittest import mock

MODULE = Path(__file__).parents[1] / "roles/hwinfo/files/hwinfo.py"
SPEC = importlib.util.spec_from_file_location("hwinfo", MODULE)
hwinfo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hwinfo)


class HwinfoCollectSudoTests(unittest.TestCase):
    def test_root_calls_dmidecode_without_sudo_wrapper(self):
        with mock.patch.object(hwinfo.os, "geteuid", return_value=0), \
             mock.patch.object(hwinfo.shutil, "which", return_value="/usr/sbin/dmidecode"), \
             mock.patch.object(hwinfo, "run", return_value=(0, "", "")) as run_mock:
            hwinfo.collect()
        dmidecode_calls = [c.args[0] for c in run_mock.call_args_list if "dmidecode" in c.args[0]]
        self.assertTrue(dmidecode_calls)
        self.assertNotIn("sudo", dmidecode_calls[0])

    def test_non_root_keeps_sudo_dash_n_wrapper(self):
        with mock.patch.object(hwinfo.os, "geteuid", return_value=1000), \
             mock.patch.object(hwinfo.shutil, "which", return_value="/usr/bin/sudo"), \
             mock.patch.object(hwinfo, "run", return_value=(0, "", "")) as run_mock:
            hwinfo.collect()
        dmidecode_calls = [c.args[0] for c in run_mock.call_args_list if "dmidecode" in c.args[0]]
        self.assertTrue(dmidecode_calls)
        self.assertEqual(dmidecode_calls[0][:2], ["sudo", "-n"])


class HwinfoSanitizationTests(unittest.TestCase):
    def test_removes_unique_identifiers_and_volatile_values(self):
        source = """System Serial Number: SECRET-SERIAL
Base Board UUID: 12345678-1234-1234-1234-123456789abc
WWN: 0x5000c50012345678
MAC address: aa:bb:cc:dd:ee:ff
CPU MHz: 3200.0
Model name: Example CPU
"""
        result = hwinfo.clean("dmidecode", source)
        for secret in ("SECRET-SERIAL", "12345678-1234-1234-1234-123456789abc", "0x5000c50012345678", "aa:bb:cc:dd:ee:ff", "3200.0"):
            self.assertNotIn(secret, result)
        self.assertIn("System Serial Number: <filter>", result)
        self.assertIn("Base Board UUID: <filter>", result)
        self.assertIn("[MAC odstraněna]", result)
        self.assertIn("Model name: Example CPU", result)

    def test_masks_inxi_personal_fields(self):
        source = "\n".join(("System: Host: lada", "Machine ID: abcdef", "CPU: Example CPU"))
        result = hwinfo.clean("inxi", source)
        self.assertIn("Host: lada", result)
        self.assertIn("Example CPU", result)
        self.assertNotIn("Machine ID", result)


if __name__ == "__main__":
    unittest.main()

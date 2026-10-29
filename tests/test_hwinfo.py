import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "roles/hwinfo/files/hwinfo.py"
SPEC = importlib.util.spec_from_file_location("hwinfo", MODULE)
hwinfo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hwinfo)


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

import hashlib
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class GuardianTenantIsolation(unittest.TestCase):
    def test_legacy_relay_auth_is_limited_to_lada(self):
        for path in sorted((BASE / "host_vars").glob("*.yml")):
            config = yaml.safe_load(path.read_text()) or {}
            if config.get("guardian_relay_legacy_auth") is True:
                self.assertEqual(path.stem, "lada", path.name)

    def test_station_hmac_keys_are_unique_when_sops_decryption_is_available(self):
        if not shutil.which("sops"):
            self.skipTest("sops není dostupný")
        if not os.environ.get("SOPS_AGE_KEY_FILE") and not Path.home().joinpath(".config/sops/age/keys.txt").exists():
            self.skipTest("age identita pro SOPS není dostupná")
        files = [BASE / "host_vars" / f"{station}.sops.yaml" for station in ("lada", "vm-mint", "vm-mint-b")]
        if not all(path.is_file() for path in files):
            self.skipTest("nejsou dostupné všechny šifrované stanice")
        digests = []
        for path in files:
            result = subprocess.run(
                ["sops", "-d", "--extract", '["hmac_key"]', "--input-type", "yaml", "--output-type", "yaml", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                self.fail("SOPS dešifrace selhala")
            value = yaml.safe_load(result.stdout)
            self.assertIsInstance(value, str)
            digests.append(hashlib.sha256(value.encode()).digest())
        self.assertEqual(len(set(digests)), len(digests), "HMAC klíče stanic nejsou jedinečné")


if __name__ == "__main__":
    unittest.main()

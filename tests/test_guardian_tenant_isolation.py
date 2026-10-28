import hashlib
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
ADMIN_RECIPIENT = "age1wvl3m4stf3rccpt634jlvyyqlqaqexnq39egzxg7870hexehz37syw7ffx"
STATION_RECIPIENTS = {
    "lada": "age1z0c4ha97umqy9ted6h3s5z4c3ap598urhl4fj9pwjw3umg2a0ygqgf076h",
    "vm-mint": "age1cglhfe8cd737jr3v79w0n3y5c9f9gw55ser4hwtmj2fz9fe5g53s59qqat",
    "vm-mint-b": "age1k7qewpknga3cnc3e93paz7eteqn8pgcr495u8e0fucelmj2f4vpsw0sy9e",
}


class GuardianTenantIsolation(unittest.TestCase):
    def test_legacy_relay_auth_is_limited_to_lada(self):
        for path in sorted((BASE / "host_vars").glob("*.yml")):
            config = yaml.safe_load(path.read_text()) or {}
            if config.get("guardian_relay_legacy_auth") is True:
                self.assertEqual(path.stem, "lada", path.name)

    def test_sops_station_recipients_are_isolated(self):
        config = yaml.safe_load((BASE / ".sops.yaml").read_text())
        rules = config["creation_rules"]

        def recipients_for(path):
            matches = [rule for rule in rules if re.search(rule["path_regex"], path)]
            self.assertEqual(len(matches), 1, path)
            return set(matches[0]["age"].replace("\n", "").split(","))

        recipient_sets = {}
        for station, recipient in STATION_RECIPIENTS.items():
            expected = {ADMIN_RECIPIENT, recipient}
            for path in (f"secrets/{station}.enc.yaml", f"host_vars/{station}.sops.yaml"):
                actual = recipients_for(path)
                self.assertEqual(actual, expected, path)
                recipient_sets.setdefault(station, actual)

        stations = sorted(recipient_sets)
        for index, station in enumerate(stations):
            for other in stations[index + 1 :]:
                self.assertEqual(
                    recipient_sets[station] & recipient_sets[other],
                    {ADMIN_RECIPIENT},
                    f"stanice {station} a {other} sdílejí staničního příjemce",
                )

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

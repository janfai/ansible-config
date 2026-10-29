import subprocess
from pathlib import Path

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


REMOTE_SOPS_COMMAND = "sudo -n bash -c 'SOPS_AGE_KEY_FILE=/mnt/disk-pool/secrets/key.txt /mnt/disk-pool/secrets/bin/sops -d --input-type yaml --output-type yaml /dev/stdin'"
MAX_CIPHERTEXT_BYTES = 2 * 1024 * 1024


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        values = []
        for term in terms:
            path = Path(term)
            if path.is_symlink() or not path.is_file():
                raise AnsibleError("Šifrovaný soubor stanice chybí nebo není běžný soubor")
            ciphertext = path.read_bytes()
            if not ciphertext or len(ciphertext) > MAX_CIPHERTEXT_BYTES:
                raise AnsibleError("Šifrovaný soubor stanice má neplatnou velikost")
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-T",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "StrictHostKeyChecking=yes",
                        "-o",
                        "ConnectTimeout=10",
                        "home-nas",
                        REMOTE_SOPS_COMMAND,
                    ],
                    input=ciphertext,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise AnsibleError("Vzdálená dešifrace SOPS přes home-nas selhala") from exc
            if result.returncode != 0 or not result.stdout:
                raise AnsibleError("Vzdálená dešifrace SOPS přes home-nas selhala")
            try:
                values.append(result.stdout.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise AnsibleError("Výstup vzdálené dešifrace SOPS není UTF-8") from exc
        return values

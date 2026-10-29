import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BootstrapMigrationTest(unittest.TestCase):
    def test_age_identity_is_created_only_when_missing_and_kept_root_only(self):
        script = ROOT.joinpath('bootstrap.sh').read_text()
        start = script.index('if [[ ! -s /etc/ansible/age.key ]]')
        end = script.index('sops_tmp=', start)
        identity = script[start:end]
        self.assertIn('age-keygen -o /etc/ansible/age.key', identity)
        self.assertIn('chown root:root /etc/ansible/age.key', identity)
        self.assertIn('chmod 0600 /etc/ansible/age.key', identity)

    def test_existing_next_refspec_and_signature_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            target = root / 'target'
            key = root / 'key'
            def run(*argv, cwd=None):
                return subprocess.check_output(argv, cwd=cwd, stderr=subprocess.STDOUT, text=True).strip()
            run('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key))
            run('git', 'init', str(source))
            run('git', 'config', 'user.name', 'test', cwd=source)
            run('git', 'config', 'user.email', 'test@example.invalid', cwd=source)
            run('git', 'checkout', '-b', 'staging', cwd=source)
            run('git', '-c', 'gpg.format=ssh', '-c', 'user.signingkey='+str(key), 'commit', '-S', '--allow-empty', '-m', 'signed', cwd=source)
            expected = run('git', 'rev-parse', 'HEAD', cwd=source)
            run('git', 'init', str(target))
            run('git', 'remote', 'add', '-t', 'next', 'origin', str(source), cwd=target)
            trust = root / 'files'
            trust.mkdir()
            (trust / 'allowed_signers').write_text('test '+key.with_suffix('.pub').read_text())
            script = ROOT.joinpath('bootstrap.sh').read_text()
            start = script.index('if [[ ! -d /var/lib/ansible-pull/.git ]]')
            end = script.index('install -o root -g root -m 0755 /var/lib/ansible-pull/bin/ansible-pull-verified', start)
            fragment = script[start:end].replace('/var/lib/ansible-pull', str(target))
            probe = root / 'bootstrap.sh'
            probe.write_text('set -euo pipefail\nrepository="$1"\nbranch=staging\ngit_ssh_command=""\n'+fragment)
            run('bash', str(probe), str(source))
            self.assertEqual(run('git', 'rev-parse', 'HEAD', cwd=target), expected)
            self.assertEqual(run('git', 'config', '--get', 'remote.origin.fetch', cwd=target), '+refs/heads/*:refs/remotes/origin/*')
            run('git', '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-m', 'unsigned', cwd=source)
            rejected = subprocess.run(['bash', str(probe), str(source)], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(run('git', 'rev-parse', 'HEAD', cwd=target), expected)


if __name__ == '__main__':
    unittest.main()

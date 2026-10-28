import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class Mailbox(unittest.TestCase):
    def test_station_flag_and_pinned_key(self):
        play = yaml.safe_load((BASE / 'local.yml').read_text())[0]
        role = next(r for r in play['roles'] if isinstance(r, dict) and r.get('role') == 'guardian')
        self.assertIn('station_config.guardian_git_enabled', role['guardian_git_enabled'])
        tasks = yaml.safe_load((BASE / 'roles/guardian/tasks/git-mailbox.yml').read_text())
        text = str(tasks)
        self.assertIn('StrictHostKeyChecking yes', text)
        self.assertNotIn('accept-new', text)
        key = BASE / 'roles/guardian/files/guardian-known-hosts'
        result = subprocess.check_output(['ssh-keygen', '-lf', str(key)], text=True)
        self.assertIn('SHA256:UB5t/EXvsOuIsJ5xISsRZQoBao7WxxIwr3UfKVoJ83E', result)

    def test_initialization_preserves_offline_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bare = root / 'bare'
            subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
            seed = root / 'seed'
            subprocess.run(['git', 'clone', str(bare), str(seed)], check=True, capture_output=True)
            def git(repo, *args):
                return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
            git(seed, '-c', 'user.name=test', '-c', 'user.email=test@localhost', 'commit', '--allow-empty', '-m', 'init')
            git(seed, 'push', 'origin', 'HEAD:master')
            station = root / 'station'
            (station / 'results').mkdir(parents=True)
            saved = station / 'results/offline.json'
            saved.write_text('{"status":"ok"}')
            tasks = yaml.safe_load((BASE / 'roles/guardian/tasks/git-mailbox.yml').read_text())
            block = next(t['block'] for t in tasks if 'block' in t)
            for task in block:
                if 'ansible.builtin.command' not in task:
                    continue
                argv = task['ansible.builtin.command']['argv']
                argv = [str(x).replace('/var/lib/guardian/repo', str(station)) for x in argv]
                argv = [str(bare) if x.startswith('guardian-git-vps:') else x for x in argv]
                subprocess.run(argv, check=True, capture_output=True)
            self.assertEqual(saved.read_text(), '{"status":"ok"}')
            git(station, 'rev-parse', '--verify', 'master')
            git(station, 'add', '-A')
            git(station, '-c', 'user.name=test', '-c', 'user.email=test@localhost', 'commit', '-m', 'offline result')
            git(station, 'push', 'origin', 'master')


if __name__ == '__main__':
    unittest.main()

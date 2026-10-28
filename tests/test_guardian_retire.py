import unittest
from pathlib import Path

import yaml


class Retire(unittest.TestCase):
    def test_logout_precedes_profile_and_account_removal(self):
        tasks = yaml.safe_load((Path(__file__).resolve().parents[1] / 'roles/guardian/tasks/main.yml').read_text())
        logout = next(i for i, t in enumerate(tasks) if isinstance(t.get('ansible.builtin.command'), dict) and t['ansible.builtin.command'].get('argv', [])[-1:] == ['logout'])
        remove_files = next(i for i, t in enumerate(tasks) if t['name'] == 'Odstranit soubory a profily Guardiana')
        remove_user = next(i for i, t in enumerate(tasks) if t.get('ansible.builtin.user', {}).get('state') == 'absent')
        self.assertLess(logout, remove_files)
        self.assertLess(remove_files, remove_user)
        self.assertIn('codex-home', tasks[logout]['environment']['CODEX_HOME'])
        self.assertEqual(tasks[logout]['become_user'], 'guardian-agent')
        self.assertTrue(tasks[logout]['no_log'])


if __name__ == '__main__':
    unittest.main()

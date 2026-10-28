import unittest
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]


class InitramfsResume(unittest.TestCase):
    def test_active_swap_uuids_are_checked_and_no_uuid_removes_stale_file(self):
        tasks = yaml.safe_load((BASE / 'roles/common/tasks/main.yml').read_text())
        handlers = yaml.safe_load((BASE / 'roles/common/handlers/main.yml').read_text())
        self.assertTrue(any(task['name'] == 'Načíst systemd' for task in handlers))
        self.assertTrue(any(task['name'] == 'Vygenerovat české prostředí' for task in handlers))
        blkid = next(task for task in tasks if task['name'] == 'Read UUIDs of active swap block devices')
        replace = next(task for task in tasks if task['name'] == 'Replace stale initramfs resume UUID with an active swap UUID')
        remove = next(task for task in tasks if task['name'] == 'Remove initramfs resume configuration without an active swap UUID')
        self.assertEqual(blkid['ansible.builtin.command']['argv'][0], 'blkid')
        self.assertTrue(any('resume_configured_uuids | intersect(resume_active_swap_uuids)' in condition for condition in replace['when']))
        self.assertIn('resume_active_swap_uuids | length == 0', remove['when'])
        self.assertEqual(remove['ansible.builtin.file']['state'], 'absent')
        self.assertEqual(replace['notify'], 'Regenerate initramfs after resume config change')
        update = next(task for task in handlers if task['name'] == 'Regenerate initramfs after resume config change')
        self.assertEqual(update['ansible.builtin.command']['argv'], ['update-initramfs', '-u'])


if __name__ == '__main__':
    unittest.main()

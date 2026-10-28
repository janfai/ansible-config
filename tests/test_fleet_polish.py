import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class FleetPolish(unittest.TestCase):
    def test_reporting_key_creation_relies_on_creates_idempotence(self):
        tasks = (BASE / 'roles/reporting/tasks/main.yml').read_text()
        task = tasks.split('- name: Vytvořit omezený SSH klíč pro odesílání přehledů', 1)[1]
        task = task.split('\n- name:', 1)[0]
        self.assertIn('creates: /var/lib/stanice-report/id_ed25519', task)
        self.assertNotIn('changed_when:', task)
        self.assertNotIn('register:', task)

    def test_pull_timer_has_calendar_fallback_and_is_deployed_by_common_role(self):
        timer = (BASE / 'systemd/ansible-pull.timer').read_text()
        self.assertIn('OnBootSec=3min', timer)
        self.assertIn('OnCalendar=*:0/15', timer)
        self.assertIn('OnUnitActiveSec=15min', timer)
        self.assertIn('RandomizedDelaySec=2min', timer)
        self.assertIn('Persistent=true', timer)
        tasks = (BASE / 'roles/common/tasks/main.yml').read_text()
        self.assertIn('src: "{{ playbook_dir }}/systemd/ansible-pull.timer"', tasks)
        self.assertIn('name: ansible-pull.timer\n    enabled: true\n    state: started', tasks)


if __name__ == '__main__':
    unittest.main()

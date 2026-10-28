import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class TimerGuard(unittest.TestCase):
    def test_timer_restored_after_success_failure_and_exception(self):
        for outcome in ('completed', 'blocked_waiting_instructions', 'exception'):
            api = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'roles/guardian/files/guardian'))
            calls = []
            def run(argv, timeout):
                calls.append(argv[1:])
                return (0, 'inactive') if argv[1] == 'show' else (0, '')
            def steps(*args):
                self.assertEqual(calls[-2][0], 'mask')
                if outcome == 'exception':
                    raise ValueError('interrupted')
                return outcome, {}
            with patch.dict(api['execute_upgrade'].__globals__, NO_SYSTEMD=False, run=run, execute_upgrade_steps=steps):
                if outcome == 'exception':
                    with self.assertRaises(ValueError):
                        api['execute_upgrade']({})
                else:
                    self.assertEqual(api['execute_upgrade']({})[0], outcome)
            self.assertEqual(calls[-2:], [['unmask', '--runtime', 'ansible-pull.timer'], ['start', 'ansible-pull.timer']])

    def test_running_pull_blocks_upgrade_and_restores_timer(self):
        api = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'roles/guardian/files/guardian'))
        calls = []
        def run(argv, timeout):
            calls.append(argv[1:])
            return 0, 'activating' if argv[1] == 'show' else ''
        with patch.dict(api['execute_upgrade'].__globals__, NO_SYSTEMD=False, run=run, execute_upgrade_steps=lambda *args: self.fail('upgrade ran')):
            self.assertEqual(api['execute_upgrade']({})[0], 'blocked_waiting_instructions')
        self.assertEqual(calls[-1], ['start', 'ansible-pull.timer'])


if __name__ == '__main__':
    unittest.main()

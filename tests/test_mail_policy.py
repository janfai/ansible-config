import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from jinja2 import Environment, StrictUndefined

BASE = Path(__file__).resolve().parents[1]


class MailPolicy(unittest.TestCase):
    def test_vm_mint_b_disables_mail_and_role_selects_denied_policy(self):
        host = yaml.safe_load((BASE / 'host_vars/vm-mint-b.yml').read_text())
        self.assertIs(host['mail_enabled'], False)
        tasks = yaml.safe_load((BASE / 'roles/mail/tasks/main.yml').read_text())
        self.assertIn('station_config.mail_enabled', tasks[0]['when'])
        self.assertIn('not (station_config.mail_enabled', tasks[1]['when'])

    def test_denied_postfix_template_cannot_route_to_a_smarthost(self):
        template = (BASE / 'roles/mail/templates/disabled-main.cf.j2').read_text()
        rendered = Environment(undefined=StrictUndefined).from_string(template).render(station_id='vm-mint-b')
        settings = {key.strip(): value.strip() for line in rendered.splitlines() for key, separator, value in [line.partition('=')] if separator}
        self.assertEqual(settings['relayhost'], '')
        self.assertEqual(settings['smtp_sasl_auth_enable'], 'no')
        self.assertEqual(settings['smtp_sasl_password_maps'], '')
        self.assertEqual(settings['smtp_generic_maps'], '')
        self.assertTrue(settings['default_transport'].startswith('error:5.7.1 '))
        self.assertTrue(settings['relay_transport'].startswith('error:5.7.1 '))
        self.assertEqual(settings['transport_maps'], '')
        self.assertNotIn('SMTP_RELAY_HOST', rendered)

    def test_reporting_mail_is_suppressed_for_boolean_and_string_false(self):
        reporting_dir = BASE / 'roles/reporting/files'
        sys.path.insert(0, str(reporting_dir))
        module_path = reporting_dir / 'reporting.py'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings_path = root / 'settings.json'
            state_path = root / 'state.json'
            for disabled in (False, 'false'):
                settings_path.write_text(json.dumps({'mail_enabled': disabled}))
                with patch.dict(os.environ, {
                    'STANICE_REPORT_STATION_ID': 'vm-mint-b',
                    'STANICE_REPORT_SETTINGS': str(settings_path),
                    'STANICE_REPORT_STATE': str(state_path),
                }, clear=False):
                    spec = importlib.util.spec_from_file_location('reporting_test_module', module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                with patch.object(module.subprocess, 'run') as run:
                    module.send(['admin@example.invalid'], 'test', 'test')
                    run.assert_not_called()
        sys.path.remove(str(reporting_dir))

    def test_ansible_failure_handler_skips_mail_when_disabled(self):
        handler = (BASE / 'roles/reporting/files/ansible-pull-failed').read_text()
        self.assertIn("settings.get('mail_enabled', True)", handler)
        self.assertIn('raise SystemExit(0)', handler)


if __name__ == '__main__':
    unittest.main()

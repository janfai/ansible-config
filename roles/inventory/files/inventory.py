#!/usr/bin/env python3
import email.message
import json
import subprocess
from pathlib import Path

station = Path('/etc/ansible/station-id').read_text().strip()
settings = json.loads(Path('/etc/ansible/reporting.json').read_text())
marker = Path('/var/lib/stanice/inventory-sent')
if marker.exists():
    raise SystemExit(10)

def output(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return result.stdout.strip().splitlines() if result.returncode == 0 else []

try:
    baseline = set(Path('/usr/share/stanice/mint-clean-manual.txt').read_text().split())
except OSError:
    baseline = set()
if 'BASELINE_PENDING' in baseline or not baseline:
    print('Referenční seznam čisté instalace Mintu zatím není připraven.')
    raise SystemExit(11)
manual = set(output(['apt-mark', 'showmanual']))
packages = sorted(manual - baseline)
services = sorted(line.split()[0] for line in output(['systemctl', 'list-units', '--type=service', '--state=running', '--no-legend']) if line.split())
timers = sorted(line.split()[0] for line in output(['systemctl', 'list-unit-files', '--type=timer', '--state=enabled', '--no-legend']) if line.split())
repo_lines = []
source_files = [Path('/etc/apt/sources.list'), *Path('/etc/apt/sources.list.d').glob('*')]
for path in source_files:
    if path.is_file():
        for line in path.read_text(errors='replace').splitlines():
            text = line.strip()
            if text.startswith('deb ') and any(token in text for token in ('ppa.launchpad', 'packages.linuxmint.com', 'archive.ubuntu.com', 'security.ubuntu.com')) is False:
                repo_lines.append(text)
inventory = {'station_id': station, 'manual_packages_above_clean_mint': packages, 'running_services': services, 'enabled_timers': timers, 'nonstandard_repositories': sorted(set(repo_lines))}
path = Path('/var/lib/stanice/inventory.json')
path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
path.chmod(0o640)
body = 'Inventář stanice ' + station + ': ' + str(len(packages)) + ' dodatečných balíčků, ' + str(len(services)) + ' běžících služeb, ' + str(len(timers)) + ' zapnutých časovačů a ' + str(len(set(repo_lines))) + ' nestandardních zdrojů balíčků.\n'
message = email.message.EmailMessage()
message['To'] = settings['admin_email']
message['Subject'] = 'První inventář stanice ' + station
message.set_content(body)
message.add_attachment(path.read_bytes(), maintype='application', subtype='json', filename='inventory.json')
subprocess.run(['/usr/sbin/sendmail', '-t'], input=message.as_bytes(), check=True)
marker.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
marker.touch(mode=0o600)
raise SystemExit(0)

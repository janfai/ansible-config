#!/usr/bin/env python3
import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path('/var/lib/stanice-report')
REPO = ROOT / 'git'
KEY = ROOT / 'id_ed25519'
KNOWN_HOSTS = ROOT / 'known_hosts'
STATION_FILE = ROOT / 'station-id'

def run(args, timeout=120, env=None):
    try:
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False, env=env)
        return result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, '', str(exc)

def clean(name, value):
    lines = []
    for line in value.splitlines():
        low = line.lower()
        identifier = re.search(r'\b(serial number|serial no\.?|system serial|chassis serial|base board serial|asset tag|wwn|uuid|machine id)\b', low)
        if name == 'dmidecode' and identifier:
            line = re.sub(r'(?i)^(\s*[^:]+:\s*).+$', r'\1<filter>', line)
        elif identifier:
            continue
        line = re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b', '[MAC odstraněna]', line)
        if re.search(r'\b(uptime|temperature|cpu mhz|bogomips|power_on_hours|power_on_hours_and|power_cycle_count|unsafe_shutdowns)\b', low):
            continue
        if name == 'inxi' and re.search(r'\b(temp|battery|health|uptime)\b', low):
            continue
        lines.append(line.rstrip())
    return '\n'.join(lines).strip() + '\n' if lines else ''

def collect():
    # Jako root (typicky Ansible become) sudo nic nepřidá a jen ho to zbytečně vystavuje
    # vlastnímu sudoers ověření (na některých stanicích i root bez tty/NOPASSWD selže);
    # dmidecode/smartctl se pak volá přímo. Mimo root (ruční spuštění) zůstává sudo -n
    # s případnou NOPASSWD výjimkou pro tyto dva konkrétní čtecí příkazy.
    as_root = os.geteuid() == 0
    sudo_prefix = [] if as_root else ['sudo', '-n']
    sudo_ok = as_root or (shutil.which('sudo') and run(['sudo', '-n', 'true'], timeout=10)[0] == 0)
    specs = {
        'inxi': ['inxi', '-Fz'],
        'dmidecode': sudo_prefix + ['dmidecode', '--type', 'bios', '--type', 'baseboard', '--type', 'system'],
        'lscpu': ['lscpu'],
        'lsblk': ['lsblk', '-e7', '-o', 'NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL'],
        'lspci': ['lspci', '-nn'],
        'lsusb': ['lsusb'],
    }
    if sudo_ok:
        if not shutil.which('dmidecode'):
            specs.pop('dmidecode')
        if shutil.which('smartctl'):
            specs['smartctl'] = sudo_prefix + ['smartctl', '--scan-open']
    else:
        specs.pop('dmidecode')
    result = {}
    for name, args in specs.items():
        prog = next((a for a in args if a not in ('sudo', '-n')), args[0])
        if not shutil.which(prog):
            continue
        if name == 'smartctl':
            code, devices, _ = run(args)
            outputs = []
            if code == 0:
                for line in devices.splitlines():
                    device = line.split()[0] if line.split() else ''
                    if device.startswith('/dev/'):
                        rc, out, _ = run(sudo_prefix + ['smartctl', '-i', '-H', device])
                        if out:
                            outputs.append(f'## {device}\n{out}')
            output = '\n'.join(outputs)
        else:
            code, output, _ = run(args)
        value = clean(name, output) if output else ''
        if value:
            result[f'{name}.txt'] = value
    return result

def main():
    station = STATION_FILE.read_text().strip()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', station):
        raise SystemExit('Neplatné ID stanice')
    REPO.mkdir(parents=True, exist_ok=True)
    if not (REPO / '.git').exists():
        code, output, error = run(['git', '-C', str(REPO), 'init', '--initial-branch=main'])
        if code:
            raise SystemExit((error or output).strip())
    remote = f'ssh://fleet-reports@vps.faix.cz:10022/srv/fleet-reports/reports-{station}.git'
    code, current, _ = run(['git', '-C', str(REPO), 'remote', 'get-url', 'origin'])
    if code:
        code, output, error = run(['git', '-C', str(REPO), 'remote', 'add', 'origin', remote])
    elif current.strip() != remote:
        code, output, error = run(['git', '-C', str(REPO), 'remote', 'set-url', 'origin', remote])
    if code:
        raise SystemExit((error or output).strip())
    reports = collect()
    latest = {}
    base = REPO / 'reports' / 'hwinfo'
    snapshots = sorted(path for path in base.glob('*/') if path.is_dir())
    if snapshots:
        for file in snapshots[-1].glob('*.txt'):
            latest[file.name] = file.read_text(errors='replace')
    env = os.environ.copy()
    env['GIT_SSH_COMMAND'] = f'ssh -i {KEY} -o IdentitiesOnly=yes -o UserKnownHostsFile={KNOWN_HOSTS} -o StrictHostKeyChecking=yes'
    if reports == latest:
        code, _, _ = run(['git', '-C', str(REPO), 'rev-parse', '--verify', 'refs/heads/main'], env=env)
        if code == 0:
            code, output, error = run(['git', '-C', str(REPO), 'push', 'origin', 'main'], timeout=180, env=env)
            if code:
                raise SystemExit((error or output).strip())
        print('beze změny')
        return
    stamp = dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    target = base / stamp
    target.mkdir(parents=True, exist_ok=False)
    for name, value in reports.items():
        (target / name).write_text(value)
    commands = [
        ['git', '-C', str(REPO), 'add', 'reports/hwinfo'],
        ['git', '-C', str(REPO), '-c', 'user.name=Stanice report', '-c', 'user.email=stanice-report@localhost', 'commit', '--only', '-m', f'HW report {station} {stamp}', '--', 'reports/hwinfo'],
        ['git', '-C', str(REPO), 'push', 'origin', 'main'],
    ]
    for command in commands:
        code, output, error = run(command, timeout=180, env=env)
        if code:
            raise SystemExit((error or output or f'příkaz selhal: {command[0]}').strip())
    print('commit vytvořen')

if __name__ == '__main__':
    main()

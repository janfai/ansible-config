#!/usr/bin/env python3
import datetime as dt
import email.message
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from station_mail_identity import station_identity

station = os.environ.get('STANICE_REPORT_STATION_ID') or Path('/etc/ansible/station-id').read_text().strip()
settings_path = os.environ.get('STANICE_REPORT_SETTINGS', '/etc/ansible/reporting.json')
settings = json.loads(Path(settings_path).read_text()) if Path(settings_path).exists() else {}
state_path = Path(os.environ.get('STANICE_REPORT_STATE', '/var/lib/stanice/reporting-state.json'))
try:
    state = json.loads(state_path.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    state = {'alerts': [], 'reminders': []}

def run(args, timeout=15, env=None):
    try:
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False, env=env)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 127, '', str(exc)

def unavailable(reason):
    return {'unavailable': reason}

def command_value(args, parser=None, timeout=15):
    code, output, error = run(args, timeout)
    if code:
        return unavailable(error or f'{args[0]} skončil s kódem {code}')
    if not parser:
        return output
    try:
        return parser(output)
    except (ValueError, TypeError, KeyError) as exc:
        return unavailable(f'výstup {args[0]} nelze zpracovat: {exc}')

def read_os_release():
    values = {}
    try:
        for line in Path(os.environ.get('STANICE_REPORT_OS_RELEASE', '/etc/os-release')).read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                values[key] = value.strip().strip('"')
    except OSError as exc:
        return unavailable(str(exc))
    version = values.get('VERSION_ID', '')
    release = '.'.join(version.split('.')[:2]) if version else None
    return {'distributor': values.get('NAME'), 'release': release, 'codename': values.get('VERSION_CODENAME') or values.get('UBUNTU_CODENAME')}

def lscpu():
    value = command_value(['lscpu', '--json'], lambda text: json.loads(text))
    if isinstance(value, dict) and 'unavailable' not in value:
        fields = {item['field'].rstrip(':'): item['data'] for item in value.get('lscpu', [])}
        try:
            cores = int(fields.get('Core(s) per socket', 0)) * int(fields.get('Socket(s)', 1))
        except (TypeError, ValueError):
            cores = fields.get('CPU(s)')
        return {'model': fields.get('Model name'), 'cores': cores, 'logical_cpus': fields.get('CPU(s)'), 'architecture': fields.get('Architecture')}
    return value

def memory():
    try:
        values = {}
        for line in Path(os.environ.get('STANICE_REPORT_MEMINFO', '/proc/meminfo')).read_text().splitlines():
            match = re.match(r'^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+)\s+kB$', line)
            if match:
                values[match.group(1)] = int(match.group(2)) * 1024
        return {'total_bytes': values.get('MemTotal'), 'available_bytes': values.get('MemAvailable'), 'swap_total_bytes': values.get('SwapTotal'), 'swap_free_bytes': values.get('SwapFree')}
    except OSError as exc:
        return unavailable(str(exc))

def machine_model():
    code, output, error = run(['dmidecode', '-s', 'system-product-name'])
    if code == 0 and output:
        return output
    try:
        return Path(os.environ.get('STANICE_REPORT_PRODUCT_NAME', '/sys/class/dmi/id/product_name')).read_text().strip()
    except OSError as exc:
        return unavailable(f'dmidecode nedostupné ({error}); sysfs: {exc}')

def disks():
    code, output, error = run(['lsblk', '-d', '-P', '-o', 'NAME,ROTA,SIZE,VENDOR,MODEL,TYPE'])
    if code:
        return unavailable(error or f'lsblk skončil s kódem {code}')
    rows = []
    for line in output.splitlines():
        values = dict(re.findall(r'(\w+)="([^"]*)"', line))
        if values.get('TYPE') != 'disk':
            continue
        if values.get('NAME', '').startswith(('zram', 'loop')):
            continue
        rows.append({'name': values.get('NAME'), 'size': values.get('SIZE'), 'vendor': values.get('VENDOR'), 'model': values.get('MODEL'), 'kind': ('HDD' if values.get('ROTA') == '1' else 'SSD/flash' if values.get('ROTA') == '0' else 'unknown')})
    return rows

def batteries():
    code, output, error = run(['upower', '-e'])
    if code:
        return unavailable(error or 'upower není dostupné')
    devices = [item for item in output.splitlines() if 'battery' in item.lower()]
    if not devices:
        return unavailable('upower nehlásí baterii')
    result = []
    for device in devices:
        code, text, error = run(['upower', '-i', device])
        if code:
            result.append(unavailable(error or f'nelze načíst {device}'))
        else:
            result.append({'device': device, 'details': text})
    return result

def filesystems():
    code, output, error = run(['df', '-PT'])
    if code:
        return unavailable(error or f'df skončil s kódem {code}')
    inode_code, inode_output, inode_error = run(['df', '-Pi'])
    inode_by_mount = {}
    if inode_code == 0:
        for line in inode_output.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 6:
                inode_by_mount[fields[-1]] = {'used': fields[2], 'free': fields[3], 'percent': fields[4]}
    result = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 7:
            continue
        mount = ' '.join(fields[6:])
        result.append({'mountpoint': mount, 'filesystem': fields[1], 'size_kib': int(fields[2]), 'used_kib': int(fields[3]), 'free_kib': int(fields[4]), 'percent': fields[5], 'inodes': inode_by_mount.get(mount, unavailable(inode_error or 'df -i nedostupné'))})
    return result

def smart():
    code, output, error = run(['lsblk', '-d', '-n', '-p', '-o', 'NAME,TYPE'])
    if code:
        return unavailable(error or 'lsblk nedostupné')
    devices = [line.split()[0] for line in output.splitlines() if len(line.split()) == 2 and line.split()[1] == 'disk' and not re.search(r'/dev/(?:zram|loop)\d+$', line.split()[0])]
    if not devices:
        return unavailable('nebyl nalezen fyzický disk')
    if not shutil.which('smartctl'):
        return {device: unavailable('smartctl není instalován') for device in devices}
    result = {}
    for device in devices:
        code, output, error = run(['smartctl', '-H', '-A', device])
        health = re.search(r'(?:SMART overall-health self-assessment test result|SMART Health Status):\s*(.+)', output)
        temperature = re.search(r'(?m)^194\s+Temperature_Celsius\s+.*?\s+(\d+)\s*$', output)
        if not temperature:
            temperature = re.search(r'(?m)^Temperature:\s*(\d+)', output)
        if code and not output:
            result[device] = unavailable(error or f'smartctl skončil s kódem {code}')
        else:
            result[device] = {'health': health.group(1).strip() if health else unavailable('smartctl neposkytl health stav'), 'temperature_celsius': int(temperature.group(1)) if temperature else unavailable('teplota SMART není dostupná'), 'detail': output if code else None}
    return result

def network():
    code, route, error = run(['ip', 'route', 'show', 'default'])
    gateway = re.search(r'\bvia\s+(\S+)', route)
    interface = re.search(r'\bdev\s+(\S+)', route)
    dns = []
    try:
        dns = re.findall(r'^nameserver\s+(\S+)', Path(os.environ.get('STANICE_REPORT_RESOLV_CONF', '/etc/resolv.conf')).read_text(), re.M)
    except OSError:
        pass
    ip_code, ip_output, ip_error = run(['ip', '-j', 'address', 'show'])
    addresses = []
    if ip_code == 0:
        try:
            for link in json.loads(ip_output):
                for info in link.get('addr_info', []):
                    if info.get('scope') == 'global':
                        address = info.get('local')
                        try:
                            public = ipaddress.ip_address(address).is_global
                        except ValueError:
                            public = unavailable('neplatná IP adresa')
                        addresses.append({'interface': link.get('ifname'), 'address': address, 'family': info.get('family'), 'public': public})
        except json.JSONDecodeError:
            pass
    nm = command_value(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'])
    return {'default_gateway': gateway.group(1) if gateway else unavailable(error or 'výchozí brána nebyla zjištěna'), 'default_interface': interface.group(1) if interface else None, 'dns_servers': dns if dns else unavailable('DNS servery nebyly zjištěny'), 'active_addresses': addresses if ip_code == 0 else unavailable(ip_error or 'ip address nedostupné'), 'network_manager': nm}

def package_state():
    code, output, error = run(['apt', 'list', '--upgradable'])
    updates = sum(1 for line in output.splitlines() if line and not line.startswith('Listing')) if code == 0 else unavailable(error or 'apt není dostupné')
    code, installed, error = run(['dpkg-query', '-W', '-f=${Version}\n', 'linux-image-[0-9]*'])
    installed_kernel = sorted(set(line for line in installed.splitlines() if line)) if code == 0 else unavailable(error or 'dpkg-query nedostupné')
    reboot = Path('/var/run/reboot-required').exists()
    return {'upgradable_count': updates, 'kernel_running': command_value(['uname', '-r']), 'kernel_installed': installed_kernel, 'reboot_required': reboot, 'last_apt_upgrade': last_upgrade()}

def last_upgrade():
    try:
        text = Path(os.environ.get('STANICE_REPORT_APT_HISTORY', '/var/log/apt/history.log')).read_text(errors='replace')
    except OSError as exc:
        return unavailable(str(exc))
    dates = []
    chunks = re.split(r'(?m)^Start-Date: ', text)
    for chunk in chunks[1:]:
        command = re.search(r'(?m)^Commandline: (.+)$', chunk)
        end = re.search(r'(?m)^End-Date: (.+)$', chunk)
        if command and end and re.search(r'upgrade|dist-upgrade|full-upgrade|unattended-upgrade', command.group(1)):
            try:
                dates.append(dt.datetime.strptime(end.group(1), '%Y-%m-%d  %H:%M:%S').isoformat())
            except ValueError:
                pass
    return max(dates) if dates else unavailable('v apt historii není záznam o dokončené aktualizaci')

def security():
    code, fail2ban_output, fail2ban_error = run(['systemctl', 'is-active', 'fail2ban'])
    fail2ban = fail2ban_output or unavailable(fail2ban_error or 'fail2ban stav nelze zjistit')
    code, output, error = run(['lastb', '-n', '100'])
    failed = sum(1 for line in output.splitlines() if line.strip() and not line.lower().startswith(('username', 'btmp begins', 'reboot '))) if code == 0 else unavailable(error or 'lastb nedostupné')
    ufw = command_value(['ufw', 'status'])
    iptables = command_value(['iptables', '-S'])
    if isinstance(iptables, str):
        rules = iptables.splitlines()
        firewall_rules = [line for line in rules if line.startswith('-A ')]
        active_policy = any(re.search(r'^-P\s+\S+\s+(DROP|REJECT)$', line) for line in rules)
        iptables_state = {'active': active_policy or bool(firewall_rules), 'rules_count': len(firewall_rules)}
    else:
        iptables_state = iptables
    firewall = {'ufw': ufw, 'iptables': iptables_state}
    return {'fail2ban': fail2ban, 'failed_login_count_recent': failed, 'firewall': firewall}

def optional_checks():
    sensors = command_value(['sensors', '-j'], lambda text: json.loads(text))
    code, output, error = run(['timeshift', '--list'], timeout=30)
    matches = re.findall(r'(?m)^\s*([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})\s+', output)
    if code:
        snapshot = unavailable(error or 'timeshift není dostupný')
    elif matches:
        latest = max(matches)
        stamp = dt.datetime.strptime(latest, '%Y-%m-%d_%H-%M-%S')
        snapshot = {'latest': latest, 'age_days': (dt.datetime.now() - stamp).days}
    else:
        snapshot = unavailable('Timeshift nehlásí žádný snapshot')
    return {'cpu_temperature': sensors, 'timeshift': snapshot}

def collect():
    os_info = read_os_release()
    if 'unavailable' in os_info:
        os_info = {'unavailable': os_info['unavailable']}
    else:
        os_info.update({'kernel': command_value(['uname', '-r']), 'architecture': command_value(['uname', '-m']), 'init_system': command_value(['systemctl', '--version'], lambda text: text.splitlines()[0] if text else 'systemd'), 'python3': sys.version.split()[0]})
    return {'schema_version': 2, 'station': station, 'collected_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'), 'os': os_info, 'hardware': {'cpu': lscpu(), 'memory': memory(), 'machine_model': machine_model(), 'disks': disks(), 'batteries': batteries()}, 'filesystems': filesystems(), 'smart': smart(), 'network': network(), 'packages': package_state(), 'security': security(), 'optional': optional_checks(), 'uptime': command_value(['uptime', '-p']), 'failed_systemd_units': command_value(['systemctl', '--failed', '--no-legend', '--plain']), 'last_ansible_pull': command_value(['systemctl', 'show', 'ansible-pull.service', '--property=Result,ExecMainStatus', '--value'])}

def flatten(value, prefix=''):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f'{prefix}{key.replace("_", " ")}: ')
    elif isinstance(value, list):
        if not value:
            yield f'{prefix}žádné'
        else:
            for item in value:
                yield from flatten(item, prefix)
    else:
        yield f'{prefix}{value}'

def markdown_report(data):
    return '# Profylaktický přehled stanice\n\n' + '\n'.join(f'- {line}' for line in flatten(data)) + '\n'

def display(value):
    return value.get('unavailable', 'nedostupné') if isinstance(value, dict) else value

def human_bytes(value):
    if not isinstance(value, int):
        return str(display(value))
    amount = float(value)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if amount < 1024 or unit == 'TiB':
            return f'{amount:.1f} {unit}'
        amount /= 1024

def email_summary(data, sync, path):
    cpu = data['hardware']['cpu']
    memory_data = data['hardware']['memory']
    filesystems_data = data['filesystems']
    if isinstance(filesystems_data, list):
        disks_used = ', '.join(f"{item['mountpoint']} {item['percent']} (volno {human_bytes(item['free_kib'] * 1024)})" for item in filesystems_data)
    else:
        disks_used = display(filesystems_data)
    smart_data = data['smart']
    if isinstance(smart_data, dict):
        smart_status = ', '.join(f'{device}: {display(value.get("health", value))}' for device, value in smart_data.items())
    else:
        smart_status = display(smart_data)
    ip_data = data['network']['active_addresses']
    addresses = ', '.join(f"{item['interface']} {item['address']}" for item in ip_data) if isinstance(ip_data, list) else display(ip_data)
    return '\n'.join([
        f"Stanice {station} — {data['collected_at']}",
        f"Systém: {data['os'].get('distributor', 'nezjištěno')} {data['os'].get('release', '')} ({data['os'].get('codename', 'bez kódového označení')}), jádro {display(data['os'].get('kernel'))}",
        f"Procesor: {display(cpu.get('model', cpu))}; jader {display(cpu.get('cores', cpu))}; paměť {human_bytes(memory_data.get('total_bytes'))}, volno {human_bytes(memory_data.get('available_bytes'))}",
        f"Oddíly: {disks_used}",
        f"Zdraví disků: {smart_status}",
        f"Aktualizace: {display(data['packages']['upgradable_count'])} čeká; restart {'je' if data['packages']['reboot_required'] else 'není'} potřeba; poslední opravy {display(data['packages']['last_apt_upgrade'])}",
        f"Síť: brána {display(data['network']['default_gateway'])}; adresy {addresses}",
        f"Neúspěšné služby: {display(data['failed_systemd_units']) or 'žádné'}; poslední ansible-pull: {display(data['last_ansible_pull'])}",
        f"Git historie: {sync}",
        f"Úplný přehled: {path}"
    ])

def git_publish(root, timestamp, json_path, md_path):
    if os.environ.get('STANICE_REPORT_SIMULATE') == '1':
        return 'simulace: vzdálený push přeskočen'
    repo = root / 'git'
    repo.mkdir(mode=0o750, parents=True, exist_ok=True)
    if not (repo / '.git').exists():
        code, output, error = run(['git', 'init', '--initial-branch=main', str(repo)])
        if code:
            return f'git init selhal: {error}'
    remote = f'ssh://fleet-reports@vps.faix.cz:10022/srv/fleet-reports/reports-{station}.git'
    code, current_remote, error = run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'])
    if code:
        code, output, error = run(['git', '-C', str(repo), 'remote', 'add', 'origin', remote])
    elif current_remote != remote:
        code, output, error = run(['git', '-C', str(repo), 'remote', 'set-url', 'origin', remote])
    if code:
        return f'git remote selhal: {error or output}'
    reports = repo / 'reports'
    reports.mkdir(exist_ok=True)
    shutil.copy2(json_path, reports / f'{timestamp}.json')
    shutil.copy2(md_path, reports / f'{timestamp}.md')
    commands = [(['git', '-C', str(repo), 'add', f'reports/{timestamp}.json', f'reports/{timestamp}.md']), (['git', '-C', str(repo), '-c', 'user.name=Stanice report', '-c', 'user.email=stanice-report@localhost', 'commit', '-m', f'Report {station} {timestamp}']), (['git', '-C', str(repo), 'push', 'origin', 'main'])]
    for args in commands:
        env = os.environ.copy()
        env['GIT_SSH_COMMAND'] = f"ssh -i {root / 'id_ed25519'} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={root / 'known_hosts'} -p 10022"
        code, output, error = run(args, timeout=60, env=env)
        if code:
            return f'{args[3] if len(args) > 3 else args[0]} selhal: {error or output}'
    return 'odesláno do Git historie'

def send(recipients, subject, body):
    message = email.message.EmailMessage()
    message['To'] = ', '.join(recipients)
    message['Subject'] = f'[{station}] {subject}'
    message.set_content(f'{body.rstrip()}\n\n{station_identity(station)}')
    subprocess.run(['/usr/sbin/sendmail', '-t'], input=message.as_bytes(), check=True)

def report():
    if os.environ.get('STANICE_REPORT_SIMULATE') == '1':
        root = Path(os.environ.get('STANICE_REPORT_ROOT', '/tmp/stanice-report-simulation'))
    else:
        root = Path('/var/lib/stanice-report')
    root.mkdir(mode=0o750, parents=True, exist_ok=True)
    data = collect()
    now = dt.datetime.now().astimezone()
    timestamp = now.strftime('%Y%m%dT%H%M%S%z')
    json_path = root / f'report-{timestamp}.json'
    md_path = root / f'report-{timestamp}.md'
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    json_path.chmod(0o640)
    md_path.write_text(markdown_report(data))
    md_path.chmod(0o640)
    sync = git_publish(root, timestamp, json_path, md_path)
    if os.environ.get('STANICE_REPORT_SIMULATE') != '1':
        send([settings['admin_email']], f'Týdenní přehled stanice {station}', email_summary(data, sync, json_path))
    return data, sync

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'weekly':
        report()
        return
    days = None
    if '--simulate-upgrade-days=' in ' '.join(sys.argv[1:]):
        days = int(next(arg.partition('=')[2] for arg in sys.argv[1:] if arg.startswith('--simulate-upgrade-days=')))
        if days < 0:
            raise SystemExit('Simulovaný počet dní nesmí být záporný.')
    current = collect()
    fs = current['filesystems']
    filesystems_by_mount = {item['mountpoint']: item for item in fs} if isinstance(fs, list) else {}
    checks = []
    alerts = set(state.get('alerts', []))
    for mount, details in filesystems_by_mount.items():
        try:
            if int(details['percent'].rstrip('%')) > 90:
                checks.append((f'filesystem:{mount}', f'Ahoj, na stanici {station} dochází místo na oddílu {mount}.\n\n{settings["admin_signature"]}'))
        except (ValueError, TypeError):
            pass
    active_filesystem_alerts = {key for key, _ in checks if key.startswith('filesystem:')}
    alerts = {key for key in alerts if not key.startswith('filesystem:') or key in active_filesystem_alerts}
    smart_results = current['smart'] if isinstance(current['smart'], dict) else {}
    if '--simulate-smart-fail' in sys.argv[1:]:
        smart_results = {'/dev/test': {'health': 'FAILED (simulace)'}}
    smart_alerts = set()
    for device, values in smart_results.items():
        health = values.get('health', {}) if isinstance(values, dict) else {}
        status = health if isinstance(health, str) else health.get('unavailable', '')
        if isinstance(status, str) and ('FAILED' in status.upper() or 'FAILING' in status.upper()):
            key = f'smart:{device}:{status}'
            smart_alerts.add(key)
            checks.append((key, f'Ahoj, kontrola našla závadu na disku stanice {station}: {device} {status}.\n\n{settings["admin_signature"]}'))
    alerts = {key for key in alerts if not key.startswith('smart:') or key in smart_alerts}
    for key, body in checks:
        if key not in alerts:
            send([settings['admin_email']], 'Upozornění: stav stanice', body)
            if settings.get('user_email') and settings['user_email'] != settings['admin_email']:
                send([settings['user_email']], 'Upozornění k počítači', 'Ahoj, počítač hlásí potíž. Ozvu se ti.\n\n' + settings['admin_signature'])
            alerts.add(key)
    upgrade = current['packages']['last_apt_upgrade']
    if days is None and isinstance(upgrade, str):
        try:
            days = (dt.datetime.now() - dt.datetime.fromisoformat(upgrade)).days
        except ValueError:
            pass
    reminders = set(state.get('reminders', []))
    if days is not None:
        for threshold in (14, 28):
            key = str(threshold)
            if days >= threshold and key not in reminders:
                send([settings.get('user_email', settings['admin_email'])], 'Připomínka péče o počítač', 'Ahoj, počítač už delší dobu neměl bezpečnostní opravy. Ozvi se mi, domluvíme se, kdy se na něj podívám.\n\n' + settings['admin_signature'])
                reminders.add(key)
        if days < 14:
            reminders.clear()
    state['reminders'] = sorted(reminders)
    state['alerts'] = sorted(alerts)
    state_path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False))
    state_path.chmod(0o600)

if __name__ == '__main__':
    main()

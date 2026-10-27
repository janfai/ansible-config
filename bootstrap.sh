#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    printf '%s\n' 'Spusťte jako root.' >&2
    exit 1
fi

station_id="${1:-}"
branch="${2:-main}"
host_fingerprint=''
if [[ "${2:-}" == SHA256:* ]] && [[ "$#" -eq 2 ]]; then
    branch='main'
    host_fingerprint="$2"
else
    host_fingerprint="${3:-}"
fi
repository="${ANSIBLE_CONFIG_REPOSITORY:-ssh://fleet-config@vps.faix.cz:10022/srv/fleet-config/ansible-config.git}"
case "${station_id}" in
    lada|milan|jitka|lucie|vlada|alan|vm-mint) ;;
    *) printf '%s\n' 'Použití: bootstrap.sh {lada|milan|jitka|lucie|vlada|alan|vm-mint} [větev] SHA256:otisk' >&2; exit 2 ;;
esac
if [[ ! "${host_fingerprint}" =~ ^SHA256:[A-Za-z0-9+/]{43}$ ]]; then
    printf '%s\n' 'Předejte ověřený fingerprint host key jako třetí parametr (SHA256:...).' >&2
    exit 2
fi

sops_version='3.13.3'
sops_sha256='e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b'
git_key='/etc/ansible/git_ed25519'
known_hosts='/etc/ansible/known_hosts'
git_ssh_command="/usr/bin/ssh -i ${git_key} -o IdentitiesOnly=yes -o UserKnownHostsFile=${known_hosts} -o StrictHostKeyChecking=yes -o BatchMode=yes"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ansible git age ca-certificates curl
if ! git check-ref-format --branch "${branch}" >/dev/null; then
    printf '%s\n' 'Neplatný název větve.' >&2
    exit 2
fi
install -d -o root -g root -m 0750 /etc/ansible
install -d -o root -g root -m 0750 /var/lib/ansible-pull

if [[ ! -s "${git_key}" ]]; then
    ssh-keygen -q -t ed25519 -N '' -C "ansible-${station_id}" -f "${git_key}"
fi
chown root:root "${git_key}" "${git_key}.pub"
chmod 0600 "${git_key}"
chmod 0644 "${git_key}.pub"

known_hosts_tmp="$(mktemp)"
trap 'rm -f "${known_hosts_tmp}"' EXIT
/usr/bin/ssh-keyscan -p 10022 -t ed25519 vps.faix.cz > "${known_hosts_tmp}" 2>/dev/null
if [[ ! -s "${known_hosts_tmp}" ]] || [[ "$(/usr/bin/ssh-keygen -lf "${known_hosts_tmp}" -E sha256 | awk 'NR == 1 {print $2}')" != "${host_fingerprint}" ]]; then
    printf '%s\n' 'Fingerprint host key VPS nesouhlasí s předanou hodnotou.' >&2
    exit 1
fi
install -o root -g root -m 0644 "${known_hosts_tmp}" "${known_hosts}"
rm -f "${known_hosts_tmp}"
trap - EXIT

if [[ -e /etc/ansible/station-id ]] && [[ "$(cat /etc/ansible/station-id)" != "${station_id}" ]]; then
    printf '%s\n' 'Soubor station-id již obsahuje jiné ID.' >&2
    exit 1
fi
printf '%s\n' "${station_id}" > /etc/ansible/station-id
chmod 0640 /etc/ansible/station-id

if [[ ! -s /etc/ansible/age.key ]]; then
    age-keygen -o /etc/ansible/age.key
fi
chown root:root /etc/ansible/age.key
chmod 0600 /etc/ansible/age.key

sops_tmp="$(mktemp)"
trap 'rm -f "${sops_tmp}"' EXIT
curl --fail --location --silent --show-error "https://github.com/getsops/sops/releases/download/v${sops_version}/sops-v${sops_version}.linux.amd64" --output "${sops_tmp}"
printf '%s  %s\n' "${sops_sha256}" "${sops_tmp}" | sha256sum --check --status
install -o root -g root -m 0755 "${sops_tmp}" /usr/local/bin/sops
rm -f "${sops_tmp}"
trap - EXIT

if [[ ! -d /var/lib/ansible-pull/.git ]]; then
    GIT_SSH_COMMAND="${git_ssh_command}" git clone --branch "${branch}" --depth 1 "${repository}" /var/lib/ansible-pull
fi
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull.service /etc/systemd/system/ansible-pull.service
printf 'ANSIBLE_CONFIG_BRANCH=%s\nANSIBLE_CONFIG_REPOSITORY=%s\nGIT_SSH_COMMAND="%s"\n' "${branch}" "${repository}" "${git_ssh_command}" > /etc/ansible/ansible-pull.env
chown root:root /etc/ansible/ansible-pull.env
chmod 0644 /etc/ansible/ansible-pull.env
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull.timer /etc/systemd/system/ansible-pull.timer
/usr/bin/ansible-galaxy collection install -p /usr/share/ansible/collections -r /var/lib/ansible-pull/collections/requirements.yml
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull-failure.service /etc/systemd/system/ansible-pull-failure.service
systemctl daemon-reload
systemctl enable --now ansible-pull.timer

printf 'Veřejný klíč age této stanice: '
age-keygen -y /etc/ansible/age.key
printf 'Veřejný Git klíč pro fleet-enroll (%s):\n' "${station_id}"
cat "${git_key}.pub"

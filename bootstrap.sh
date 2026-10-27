#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    printf '%s\n' 'Spusťte jako root.' >&2
    exit 1
fi

station_id="${1:-}"
branch="${2:-main}"
case "${station_id}" in
    lada|milan|jitka|lucie|vlada|alan|vm-mint) ;;
    *) printf '%s\n' 'Použití: bootstrap.sh {lada|milan|jitka|lucie|vlada|alan|vm-mint} [main|next]' >&2; exit 2 ;;
esac
if ! git check-ref-format --branch "${branch}" >/dev/null; then
    printf '%s\n' 'Neplatný název větve.' >&2
    exit 2
fi

sops_version='3.13.3'
sops_sha256='e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b'
repository="${ANSIBLE_CONFIG_REPOSITORY:-ssh://fleet-config@vps.faix.cz:10022/srv/fleet-config/ansible-config.git}"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ansible git age ca-certificates curl
install -d -o root -g root -m 0750 /etc/ansible
install -d -o root -g root -m 0750 /var/lib/ansible-pull
install -d -o root -g root -m 0750 /var/lib/ansible-pull-state

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
    git clone --branch "${branch}" --depth 1 "${repository}" /var/lib/ansible-pull
fi
install -o root -g root -m 0755 /var/lib/ansible-pull/bin/ansible-pull-verified /usr/local/sbin/ansible-pull-verified
install -o root -g root -m 0750 /var/lib/ansible-pull/roles/reporting/files/ansible-pull-failed /usr/local/sbin/ansible-pull-failed
install -o root -g root -m 0750 /var/lib/ansible-pull/roles/reporting/files/ansible-pull-succeeded /usr/local/sbin/ansible-pull-succeeded
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull.service /etc/systemd/system/ansible-pull.service
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull-failure.service /etc/systemd/system/ansible-pull-failure.service
install -d -o root -g root -m 0750 /var/lib/stanice
printf 'ANSIBLE_CONFIG_BRANCH=%s\nANSIBLE_CONFIG_REPOSITORY=%s\n' "${branch}" "${repository}" > /etc/ansible/ansible-pull.env
chown root:root /etc/ansible/ansible-pull.env
chmod 0644 /etc/ansible/ansible-pull.env
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull.timer /etc/systemd/system/ansible-pull.timer
/usr/bin/ansible-galaxy collection install -p /usr/share/ansible/collections -r /var/lib/ansible-pull/collections/requirements.yml
install -o root -g root -m 0644 /var/lib/ansible-pull/systemd/ansible-pull-failure.service /etc/systemd/system/ansible-pull-failure.service
systemctl daemon-reload
systemctl enable --now ansible-pull.timer

printf 'Veřejný klíč age této stanice: '
age-keygen -y /etc/ansible/age.key

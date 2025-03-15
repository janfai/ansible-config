#!/bin/bash
# Bootstrap skript pro nastavení Ansible Pull

# Kontrola, zda je skript spuštěn s právy roota
if [ "$(id -u)" -ne 0 ]; then
    echo "Tento skript musí být spuštěn jako root nebo s sudo."
    exit 1
fi

# Nastavení proměnných
GIT_REPO="https://github.com/vas-uzivatel/ansible-config.git"
GIT_BRANCH="main"
ANSIBLE_DIR="/var/lib/ansible"
LOG_DIR="/var/log/ansible"
LOG_FILE="${LOG_DIR}/ansible-pull.log"
CRON_SCHEDULE="30 * * * *"  # Každou hodinu v 30. minutě

# Instalace závislostí
apt-get update
apt-get install -y git ansible

# Vytvoření adresářů
mkdir -p "${ANSIBLE_DIR}" "${LOG_DIR}"
chmod 750 "${LOG_DIR}"

# Vytvoření cron úlohy
cat > /etc/cron.d/ansible-pull << EOL
# Ansible Pull - pravidelná aktualizace konfigurace
${CRON_SCHEDULE} root ansible-pull -U ${GIT_REPO} -C ${GIT_BRANCH} -d ${ANSIBLE_DIR} > ${LOG_FILE} 2>&1
EOL

# První spuštění
echo "Provádím první pull a konfiguraci..."
ansible-pull -U "${GIT_REPO}" -C "${GIT_BRANCH}" -d "${ANSIBLE_DIR}" | tee -a "${LOG_FILE}"

echo "Konfigurace dokončena. Ansible-pull je nastaven pro automatické spouštění."
echo "Logy můžete sledovat v ${LOG_FILE}"

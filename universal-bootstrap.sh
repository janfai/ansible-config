#!/bin/bash
# universal-bootstrap.sh

set -euo pipefail

# Výchozí hodnoty parametrů
DEFAULT_INVENTORY="inventories/default"
DEFAULT_PLAYBOOK="playbooks/default.yml"
DEFAULT_VAULT_PASS_FILE="/etc/ansible/.vault_pass"

# Zpracování parametrů
while getopts ":i:p:v:" opt; do
  case $opt in
    i) INVENTORY="$OPTARG" ;;
    p) PLAYBOOK="$OPTARG" ;;
    v) VAULT_PASS_FILE="$OPTARG" ;;
    \?) echo "Neplatná možnost: -$OPTARG" >&2; exit 1 ;;
    :) echo "Možnost -$OPTARG vyžaduje argument." >&2; exit 1 ;;
  esac
done

# Nastavení výchozích hodnot
INVENTORY="${INVENTORY:-$DEFAULT_INVENTORY}"
PLAYBOOK="${PLAYBOOK:-$DEFAULT_PLAYBOOK}"
VAULT_PASS_FILE="${VAULT_PASS_FILE:-$DEFAULT_VAULT_PASS_FILE}"

ANSIBLE_DIR="/var/lib/ansible"
BOOTSTRAP_FLAG="/etc/ansible/bootstrap_completed"

# Kontrola dokončení
if [ -f "$BOOTSTRAP_FLAG" ]; then
    echo "Bootstrap již byl proveden. Pro opětovné spuštění odstraňte $BOOTSTRAP_FLAG"
    exit 0
fi

# Instalace závislostí
sudo apt update && sudo apt install -y git ansible

# Nastavení adresářů
sudo mkdir -p "$ANSIBLE_DIR" "/etc/ansible"
sudo chmod 750 "$ANSIBLE_DIR"
sudo chown -R root:root "$ANSIBLE_DIR" "/etc/ansible"

# Získání hesla pro Vault
if [ ! -f "$VAULT_PASS_FILE" ]; then
    echo "Zadejte heslo pro Ansible Vault:"
    read -s -r VAULT_PASS
    echo "Zadejte heslo znovu pro ověření:"
    read -s -r VAULT_PASS_CONFIRM

    if [ "$VAULT_PASS" != "$VAULT_PASS_CONFIRM" ]; then
        echo "Chyba: Hesla se neshodují!"
        exit 1
    fi

    echo "$VAULT_PASS" | sudo tee "$VAULT_PASS_FILE" >/dev/null
    sudo chmod 600 "$VAULT_PASS_FILE"
    unset VAULT_PASS VAULT_PASS_CONFIRM
fi

# Klonování/aktualizace repozitáře
if [ -d "$ANSIBLE_DIR/.git" ]; then
    sudo git -C "$ANSIBLE_DIR" pull --force
else
    sudo git clone https://github.com/janfai/ansible-config.git "$ANSIBLE_DIR"
fi

# Spuštění Ansible
sudo ansible-pull \
  -U https://github.com/janfai/ansible-config.git \
  -d "$ANSIBLE_DIR" \
  -i "$INVENTORY" \
  --vault-password-file "$VAULT_PASS_FILE" \
  "$PLAYBOOK"

# Označení úspěchu
sudo touch "$BOOTSTRAP_FLAG"
echo "Bootstrap úspěšně dokončen!"

#!/bin/bash
# bootstrap-vm-mint.sh

set -euo pipefail

# Adresáře
ANSIBLE_DIR="/var/lib/ansible"
VAULT_PASS_FILE="$ANSIBLE_DIR/.vault_pass"
BOOTSTRAP_FLAG="$ANSIBLE_DIR/bootstrap_completed"

# Kontrola, zda již bootstrap nebyl spuštěn
if [ -f "$BOOTSTRAP_FLAG" ]; then
    echo "Bootstrap již byl úspěšně dokončen. Pro opětovné spuštění nejprve odstraňte $BOOTSTRAP_FLAG"
    exit 0
fi

# Instalace závislostí
sudo apt update && sudo apt install -y git ansible

# Vytvoření adresářů
sudo mkdir -p "$ANSIBLE_DIR"
sudo chmod 750 "$ANSIBLE_DIR"

# Generování náhodného hesla pro Vault (pouze při prvním spuštění)
if [ ! -f "$VAULT_PASS_FILE" ]; then
    echo "Generuji nové náhodné heslo pro Ansible Vault..."
    VAULT_PASS=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 32)
    echo "$VAULT_PASS" | sudo tee "$VAULT_PASS_FILE" >/dev/null
    sudo chmod 600 "$VAULT_PASS_FILE"
    echo "HESLO PRO ANSIBLE VAULT: $VAULT_PASS"
    echo "Toto heslo si poznamenejte a bezpečně uložte. Nebude zobrazeno znovu!"
fi

# Klonování repozitáře
sudo git -C "$ANSIBLE_DIR" clone https://github.com/janfai/ansible-config.git .

# Čištění při chybě
cleanup() {
    echo "Čištění po chybě..."
    sudo rm -rf "$VAULT_PASS_FILE" "$BOOTSTRAP_FLAG"
    exit 1
}
trap cleanup ERR

# Spuštění Ansible
sudo ansible-pull \
  -U https://github.com/janfai/ansible-config.git \
  -i inventories/vm-mint \
  --vault-password-file "$VAULT_PASS_FILE" \
  playbooks/vm-mint.yml

# Označení úspěšného dokončení
sudo touch "$BOOTSTRAP_FLAG"
echo "Bootstrap úspěšně dokončen. Pro opětovné spuštění odstraňte $BOOTSTRAP_FLAG"
